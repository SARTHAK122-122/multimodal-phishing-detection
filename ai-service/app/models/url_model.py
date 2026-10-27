"""URL-modality inference over the trained RandomForest + XGBoost bundles.

Loads artifacts produced by ``training/train_url_models.py`` and returns a
calibrated-free (but well-behaved) phishing probability plus per-feature SHAP
contributions for explainability. Nothing here trains or invents - if an
artifact is missing the modality is reported as ``MODEL_MISSING``.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from app.inference import model_registry
from app.ml.url_features import FEATURE_NAMES, extract_features

# Which artifacts participate in the URL ensemble, and their display metadata.
ENSEMBLE = ["url_random_forest", "url_xgboost"]

_LOCK = threading.Lock()
_CACHE: Dict[str, object] = {}
_SHAP_CACHE: Dict[str, object] = {}


@dataclass
class UrlPrediction:
    ok: bool
    probability: Optional[float] = None          # mean P(phishing) across loaded models
    per_model: List[dict] = field(default_factory=list)
    contributors: List[dict] = field(default_factory=list)  # SHAP top features
    models_used: List[str] = field(default_factory=list)
    models_missing: List[str] = field(default_factory=list)
    detail: str = ""


def _load(name: str):
    """Load and cache a joblib bundle, or return None. Thread-safe."""
    if name in _CACHE:
        return _CACHE[name]
    if not model_registry.is_available(name):
        return None
    import joblib  # heavy import, deferred
    try:
        bundle = joblib.load(model_registry.artifact_path(name))
    except Exception:
        return None
    with _LOCK:
        _CACHE[name] = bundle
    return bundle


def available_models() -> List[str]:
    return [m for m in ENSEMBLE if _load(m) is not None]


def _bundle_feature_order(bundle) -> List[str]:
    """Feature order stored inside the bundle (source of truth for that model).

    Falls back to the current module-level FEATURE_NAMES only if the bundle has
    no stored order, so a model trained on an older schema still scores.
    """
    order = bundle.get("features") if isinstance(bundle, dict) else None
    return list(order) if order else list(FEATURE_NAMES)


def predict(url: str) -> UrlPrediction:
    """Predict P(phishing) for a URL using every available ensemble member."""
    feats = extract_features(url)

    probabilities: List[float] = []
    per_model: List[dict] = []
    missing: List[str] = []
    used: List[str] = []
    top_contributors: List[dict] = []

    for name in ENSEMBLE:
        bundle = _load(name)
        if bundle is None:
            missing.append(name)
            continue
        model = bundle["model"]
        order = _bundle_feature_order(bundle)
        # Build the row in THIS bundle's feature order (may be v1 or v2 schema).
        row = np.array([[feats.get(f, 0.0) for f in order]], dtype=float)
        try:
            proba = float(model.predict_proba(row)[0, 1])
        except Exception as exc:
            per_model.append({"model": name, "error": exc.__class__.__name__})
            continue
        probabilities.append(proba)
        used.append(name)
        meta = model_registry.load_metadata(name) or {}
        per_model.append({
            "model": name,
            "probability": round(proba, 4),
            "metrics": meta.get("metrics"),
            "trainedAt": meta.get("trainedAt"),
        })

        # SHAP contributions from the first successful model (TreeExplainer).
        if not top_contributors:
            top_contributors = _shap_contributors(name, model, row, feats, order)

    if not probabilities:
        return UrlPrediction(
            ok=False,
            per_model=per_model,
            models_missing=missing,
            detail="No URL model artifact is available; the URL modality is skipped.",
        )

    mean = float(np.mean(probabilities))
    return UrlPrediction(
        ok=True,
        probability=mean,
        per_model=per_model,
        contributors=top_contributors,
        models_used=used,
        models_missing=missing,
        detail=("Mean P(phishing) across "
                f"{len(probabilities)} tree model(s). This is a raw model score, "
                "not a calibrated probability."),
    )


def _phishing_class_values(sv) -> np.ndarray:
    """SHAP contributions toward the phishing class (index 1 of ``classes_``).

    Tree explainers return one of three shapes for a binary tree model, and
    picking the wrong slice silently flips every sign (or indexes out of range):

      * ``list`` of per-class arrays  ``[class0, class1]``
      * ``ndarray (samples, features, classes)``   (e.g. RandomForest on shap 0.46)
      * ``ndarray (samples, features)``            (single = positive class, XGBoost)
    """
    if isinstance(sv, list):
        arr = np.asarray(sv[1], dtype=float)
    else:
        arr = np.asarray(sv, dtype=float)
        if arr.ndim == 3:
            arr = arr[0, :, 1]
        elif arr.ndim == 2:
            arr = arr[0]
    return arr.reshape(-1)


def _shap_contributors(name: str, model, row, feats: Dict[str, float],
                       feature_order: List[str]) -> List[dict]:
    """Top SHAP feature contributions for one row. Returns [] if SHAP fails.

    ``feature_order`` is the model's own feature list, so contribution labels
    always match the columns the model was trained on.
    Uses TreeExplainer when importable; otherwise falls back to a transparent
    impurity-importance heuristic only if the estimator exposes
    ``feature_importances_``.

    Honesty rule: only signed SHAP values may claim a direction (``risk`` /
    ``safety``). The unsigned fallback is reported as ``neutral`` - importance
    ranks influence but cannot say which way it pushed the verdict.
    """
    key = f"{name}:{id(model)}"
    try:
        import shap  # deferred heavy import
    except Exception:
        shap = None

    if shap is not None:
        try:
            with _LOCK:
                explainer = _SHAP_CACHE.get(key)
            if explainer is None:
                explainer = shap.TreeExplainer(model)
                with _LOCK:
                    _SHAP_CACHE[key] = explainer
            values = _phishing_class_values(explainer.shap_values(row))
            if values.shape[0] != len(feature_order):
                raise ValueError(
                    f"SHAP returned {values.shape[0]} values for "
                    f"{len(feature_order)} features")
            idx = np.argsort(np.abs(values))[::-1][:8]
            return [
                {
                    "feature": feature_order[i],
                    "value": round(float(feats.get(feature_order[i], 0.0)), 4),
                    "contribution": round(float(values[i]), 5),
                    "direction": "risk" if values[i] > 0 else "safety",
                }
                for i in idx
                if values[i] != 0
            ]
        except Exception:
            pass

    # Fallback: use impurity-based feature importances (still honest, documented).
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        return []
    importances = np.asarray(importances).reshape(-1)
    idx = np.argsort(importances)[::-1][:8]
    return [
        {
            "feature": feature_order[i],
            "value": round(float(feats.get(feature_order[i], 0.0)), 4),
            "importance": round(float(importances[i]), 5),
            "direction": "neutral",
            "note": "Tree impurity importance (SHAP unavailable): ranks "
                    "influence, not direction.",
        }
        for i in idx
        if importances[i] > 0
    ]
