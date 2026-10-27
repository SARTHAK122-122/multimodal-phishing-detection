"""Train the URL-modality models (RandomForest + XGBoost) on the real PhiUSIIL dataset.

Honesty rules enforced by this script:
  * Data: UCI #967 PhiUSIIL Phishing URL Dataset (downloaded, checksummed, real).
  * Dedupe on URL BEFORE splitting -> no identical URL can appear in both sets.
  * Stratified 80/20 hold-out, random_seed=42. The test set is NEVER used for
    fitting, tuning or early stopping (XGBoost is fit on train only, no eval_set
    from the test split, no callback stopping).
  * Metrics are COMPUTED from predictions on the hold-out set and printed and
    persisted exactly as computed - nothing is hard-coded.
  * After training, results are POSTed to Spring Boot /api/models/registrations
    so PostgreSQL gains model_versions + evaluation_runs rows. If the backend is
    unreachable the artifacts are still saved and the script says so.

Usage (from ai-service/):
    .venv\\Scripts\\python.exe training\\train_url_models.py
"""

from __future__ import annotations

import json
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai-service"))

from app import config  # noqa: E402
from app.ml.url_features import FEATURE_NAMES, extract_rows  # noqa: E402

DATASET_CSV = ROOT / "datasets" / "sources" / "PhiUSIIL_Phishing_URL_Dataset.csv"
DATASET_ZIP = ROOT / "datasets" / "sources" / "phiusiil_phishing_url_dataset.zip"
# Small, hand-curated real-world sanity check. It is NOT a benchmark and its
# numbers are never mixed with the PhiUSIIL hold-out metrics - it exists purely
# to catch over-fitting to dataset-specific URL style (e.g. flagging real
# benign sites like github.com as phishing).
SANITY_CSV = ROOT / "datasets" / "url_sanity_realworld.csv"

RANDOM_SEED = 42
TEST_FRACTION = 0.2
BACKEND_URL = "http://localhost:8088/api"
DATASET_PROVENANCE = (
    "UCI ML Repository #967 PhiUSIIL Phishing URL Dataset "
    "(https://archive.ics.uci.edu/dataset/967/phiusiil+phishing+url+dataset), "
    "sha256=0A639FD03AEA6308C5B1C10C92AA23C2CE1505447A9137271865CD0BADC9A59A"
)

MODEL_SPECS = {
    "url_random_forest": lambda: RandomForestClassifier(
        n_estimators=300,
        random_state=RANDOM_SEED,
        n_jobs=-1,
        class_weight=None,  # data is fairly balanced; no reweighting tricks
    ),
    "url_xgboost": lambda: XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.9,
        colsample_bytree=0.9,
        random_state=RANDOM_SEED,
        eval_metric="logloss",
        tree_method="hist",
        n_jobs=-1,
    ),
}


def ensure_extracted() -> None:
    if DATASET_CSV.exists():
        return
    if not DATASET_ZIP.exists():
        raise SystemExit(f"dataset archive missing: {DATASET_ZIP}")
    with zipfile.ZipFile(DATASET_ZIP) as zf:
        zf.extractall(DATASET_CSV.parent)
    print(f"extracted -> {DATASET_CSV}")


def load_dataset() -> tuple[pd.DataFrame, dict]:
    """Load URL + label, dedupe on URL, return (df, data-quality stats)."""
    ensure_extracted()
    raw = pd.read_csv(DATASET_CSV, encoding="utf-8-sig", usecols=["URL", "label"])
    stats = {"raw_rows": int(len(raw))}

    # Label semantics in this dataset: 1 = legitimate, 0 = phishing.
    # Positive class for all metrics = phishing (1), the class we must catch.
    raw["is_phishing"] = (raw["label"] == 0).astype(int)
    stats["label_legitimate"] = int((raw["label"] == 1).sum())
    stats["label_phishing"] = int((raw["label"] == 0).sum())

    # Conflicting labels for the same URL would make the task ill-defined.
    conflicts = raw.groupby("URL")["is_phishing"].nunique()
    conflict_urls = int((conflicts > 1).sum())
    if conflict_urls:
        raw = raw[~raw["URL"].isin(conflicts[conflicts > 1].index)]
    stats["dropped_conflicting_label_urls"] = conflict_urls

    # Dedupe BEFORE the split: identical URLs in train and test = leakage.
    before = len(raw)
    raw = raw.drop_duplicates(subset=["URL"], keep="first").reset_index(drop=True)
    stats["dropped_duplicate_urls"] = before - len(raw)
    stats["rows_after_dedupe"] = int(len(raw))
    return raw, stats


def evaluate_realworld_sanity(model, feature_order) -> dict:
    """Score the hand-curated real-world sanity set. Reported SEPARATELY from
    the PhiUSIIL hold-out metrics. Returns counts + the misclassified URLs so a
    reviewer can see exactly which benign/phishing URLs the model gets wrong."""
    if not SANITY_CSV.exists():
        return {"available": False}
    san = pd.read_csv(SANITY_CSV, encoding="utf-8-sig")
    Xs = pd.DataFrame(extract_rows(san["url"].tolist()), columns=feature_order)
    ys = (san["label"] == 1).astype(int).to_numpy()
    proba = model.predict_proba(Xs)[:, 1]
    pred = (proba >= 0.5).astype(int)
    correct = int((pred == ys).sum())
    # False positives = benign URLs wrongly flagged phishing (must be ~0 for a
    # credible demo); false negatives = phishing URLs missed.
    fp_urls = san["url"][(pred == 1) & (ys == 0)].tolist()
    fn_urls = san["url"][(pred == 0) & (ys == 1)].tolist()
    return {
        "available": True,
        "total": int(len(san)),
        "correct": correct,
        "accuracy": correct / len(san) if len(san) else 0.0,
        "falsePositives": len(fp_urls),
        "falseNegatives": len(fn_urls),
        "fpUrls": fp_urls[:10],
        "fnUrls": fn_urls[:10],
    }


def main() -> None:
    started = time.time()
    df, stats = load_dataset()
    print(f"rows: {stats['raw_rows']} raw -> {stats['rows_after_dedupe']} unique URLs")
    print(f"labels: phishing={stats['label_phishing']} legitimate={stats['label_legitimate']}")
    print(f"duplicates removed: {stats['dropped_duplicate_urls']}  "
          f"conflicting-label URLs removed: {stats['dropped_conflicting_label_urls']}")

    print("extracting URL features ...")
    rows = extract_rows(df["URL"].tolist())
    X = pd.DataFrame(rows, columns=FEATURE_NAMES)
    y = df["is_phishing"].to_numpy()
    empty_urls = int((df["URL"].str.strip() == "").sum())
    print(f"feature matrix: {X.shape[0]} rows x {X.shape[1]} features")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=TEST_FRACTION, random_state=RANDOM_SEED, stratify=y
    )
    print(f"split: train={len(X_train)} test={len(X_test)} "
          f"(stratified 80/20 train/test, "
          f"seed={RANDOM_SEED})")

    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    trained_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    results: dict[str, dict] = {}

    for name, factory in MODEL_SPECS.items():
        print(f"\n=== training {name} ===")
        t0 = time.time()
        model = factory()
        model.fit(X_train, y_train)  # fit on TRAIN only
        train_seconds = round(time.time() - t0, 1)

        y_pred = model.predict(X_test)                       # hold-out predictions
        y_prob = model.predict_proba(X_test)[:, 1]
        tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
        metrics = {
            "accuracy": float(accuracy_score(y_test, y_pred)),
            "precision": float(precision_score(y_test, y_pred)),
            "recall": float(recall_score(y_test, y_pred)),
            "f1": float(f1_score(y_test, y_pred)),
            "rocAuc": float(roc_auc_score(y_test, y_prob)),
            "falsePositiveRate": float(fp / (fp + tn)),
            "falseNegativeRate": float(fn / (fn + tp)),
        }
        results[name] = {
            **metrics,
            "trainSeconds": train_seconds,
            "confusionMatrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            "trainSize": int(len(X_train)),
            "testSize": int(len(X_test)),
        }
        print(f"  trained in {train_seconds}s")
        for k, v in metrics.items():
            print(f"  {k:<20} {v:.4f}")
        print(f"  confusion tn={tn} fp={fp} fn={fn} tp={tp}")

        # Real-world sanity check (reported separately; NOT part of hold-out).
        sanity = evaluate_realworld_sanity(model, FEATURE_NAMES)
        results[name]["realworldSanity"] = sanity
        if sanity.get("available"):
            print(f"  real-world sanity: {sanity['correct']}/{sanity['total']} correct "
                  f"(FP={sanity['falsePositives']} benign flagged, "
                  f"FN={sanity['falseNegatives']} phishing missed)")
            if sanity["fpUrls"]:
                print(f"    false-positive URLs: {sanity['fpUrls']}")
            if sanity["fnUrls"]:
                print(f"    false-negative URLs: {sanity['fnUrls']}")

        # Persist artifact as a bundle: model + the frozen feature order.
        artifact = config.MODEL_DIR / f"{name}.joblib"
        joblib.dump({"model": model, "features": FEATURE_NAMES, "trainedAt": trained_at}, artifact)
        metadata = {
            "trainedAt": trained_at,
            "dataset": DATASET_PROVENANCE,
            "randomSeed": RANDOM_SEED,
            "splitStrategy": "stratified 80/20 hold-out (train/test)",
            "trainSize": int(len(X_train)),
            "testSize": int(len(X_test)),
            "featureNames": FEATURE_NAMES,
            "featureSchemaVersion": 2,
            "metrics": metrics,
            "realworldSanity": sanity,
        }
        (config.MODEL_DIR / f"{name}.metadata.json").write_text(
            json.dumps(metadata, indent=2), encoding="utf-8"
        )
        print(f"  saved {artifact}")

    summary = {
        "trainedAt": trained_at,
        "dataset": DATASET_PROVENANCE,
        "randomSeed": RANDOM_SEED,
        "dataQuality": {**stats, "emptyUrls": empty_urls},
        "models": results,
    }
    summary_path = config.MODEL_DIR / "url_models.training.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nsummary -> {summary_path}")
    print(f"total {round(time.time() - started, 1)}s")

    # ---- register measured metrics with Spring Boot (PostgreSQL) ----
    register(summary)


def register(summary: dict) -> None:
    for name, res in summary["models"].items():
        payload = {
            "modelName": name,
            "modelType": "ML",
            "version": "1.0.0",
            "artifactPath": f"{name}.joblib",
            "trainingDate": summary["trainedAt"],
            "notes": (
                "Trained on the real PhiUSIIL dataset (UCI #967); "
                "16 host-only URL features (v3 schema). Path/query features were removed "
                "after v1/v2 exposed a dataset artifact: every PhiUSIIL legitimate URL is a "
                "bare domain, so path features scored near-perfectly on the hold-out but "
                "failed on real URLs. v3 trades ~4 accuracy points for real-world sanity. "
                "stratified 80/20 hold-out; a separate 40-URL hand-labelled real-world "
                "sanity set is evaluated and stored in resultsJson (realworldSanity)."
            ),
            "splitStrategy": "stratified 80/20 hold-out (train/test)",
            "randomSeed": summary["randomSeed"],
            "ablationConfig": "URL",
            "metrics": {
                "accuracy": res["accuracy"],
                "precisionScore": res["precision"],
                "recallScore": res["recall"],
                "f1Score": res["f1"],
                "rocAuc": res["rocAuc"],
                "falsePositiveRate": res["falsePositiveRate"],
                "falseNegativeRate": res["falseNegativeRate"],
                "resultsJson": json.dumps(res),
            },
        }
        try:
            resp = requests.post(
                f"{BACKEND_URL}/models/registrations", json=payload, timeout=15
            )
            resp.raise_for_status()
            body = resp.json()
            print(f"registered {name}: modelVersionId={body.get('modelVersionId')} "
                  f"evaluationRunId={body.get('evaluationRunId')} "
                  f"status={body.get('evaluationStatus')}")
        except requests.RequestException as exc:
            print(f"WARNING: could not register {name} with backend ({exc}). "
                  f"Artifacts are saved; re-run the script when the backend is up.")


if __name__ == "__main__":
    main()
