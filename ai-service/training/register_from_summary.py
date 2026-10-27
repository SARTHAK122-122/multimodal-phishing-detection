"""One-off: register a model from the saved training summary (no retraining).

Usage:  .venv\\Scripts\\python.exe training\\register_from_summary.py <model_name>
Used when the backend was unreachable at the end of a training run.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402
from training.train_url_models import register  # noqa: E402

name = sys.argv[1]
summary = json.loads((config.MODEL_DIR / "url_models.training.json").read_text(encoding="utf-8"))
if name not in summary["models"]:
    raise SystemExit(f"{name} not in summary; have: {list(summary['models'])}")

# Keep the corrected split label for freshly registered rows.
summary["models"] = {name: summary["models"][name]}
register(summary)
