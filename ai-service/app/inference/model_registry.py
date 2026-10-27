"""Registry of trained model artifacts.

Inference code must load artifacts from disk - it never trains, never returns
random values and never invents predictions. If an artifact is missing the
registry says so and the caller reports the modality as ``MODEL_MISSING``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from app import config

# Logical model name -> artifact file name inside MODEL_DIR.
ARTIFACTS: Dict[str, str] = {
    "url_random_forest": "url_random_forest.joblib",
    "url_xgboost": "url_xgboost.joblib",
    "html_random_forest": "html_random_forest.joblib",
    "nlp_distilbert": "nlp_distilbert",
    "vision_cnn": "vision_cnn.pt",
    "fusion_logreg": "fusion_logreg.joblib",
}


def artifact_path(model_name: str) -> Path:
    return config.MODEL_DIR / ARTIFACTS[model_name]


def metadata_path(model_name: str) -> Path:
    return config.MODEL_DIR / f"{model_name}.metadata.json"


def is_available(model_name: str) -> bool:
    path = artifact_path(model_name)
    return path.exists()


def load_metadata(model_name: str) -> Optional[Dict[str, Any]]:
    path = metadata_path(model_name)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def status() -> Dict[str, Any]:
    """Honest availability report used by /health and by the inference layer."""
    result: Dict[str, Any] = {}
    for name in ARTIFACTS:
        path = artifact_path(name)
        meta = load_metadata(name)
        result[name] = {
            "artifactPresent": path.exists(),
            "artifact": str(Path(ARTIFACTS[name])).replace("\\", "/"),
            "metrics": (meta or {}).get("metrics"),
            "trainedAt": (meta or {}).get("trainedAt"),
            "dataset": (meta or {}).get("dataset"),
        }
    return result
