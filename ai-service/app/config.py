"""Runtime configuration for the AI service.

All paths are resolved once here and every file access must go through
:func:`safe_path`, which refuses anything outside the configured storage
directories (path-traversal protection).
"""

from __future__ import annotations

import os
from pathlib import Path

# ai-service/  (this file lives in ai-service/app/)
AI_SERVICE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", AI_SERVICE_ROOT.parent)).resolve()


def _resolve_env_path(name: str, default: str) -> Path:
    """Resolve a storage path from the environment.

    ``default`` is always anchored at ``PROJECT_ROOT`` so the service behaves
    identically no matter which working directory uvicorn is started from.
    Explicit environment overrides may be absolute, or relative to
    ``PROJECT_ROOT``.
    """
    raw = os.environ.get(name)
    if raw is None:
        return (PROJECT_ROOT / default).resolve()
    path = Path(raw)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path.resolve()


# All three defaults are relative to the project root (the parent of ai-service/),
# which keeps Java (Spring) and Python pointed at the SAME directories.
UPLOAD_DIR = _resolve_env_path("UPLOAD_DIR", "uploads")
PROCESSED_DIR = _resolve_env_path("PROCESSED_DIR", "uploads/processed")
MODEL_DIR = _resolve_env_path("MODEL_DIR", "models")

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(50 * 1024 * 1024)))

# Webpage acquisition safety limits
MAX_FETCH_BYTES = int(os.environ.get("MAX_FETCH_BYTES", "2000000"))
MAX_REDIRECTS = int(os.environ.get("MAX_REDIRECTS", "3"))
FETCH_TIMEOUT_SECONDS = int(os.environ.get("FETCH_TIMEOUT_SECONDS", "15"))
ENABLE_SCREENSHOTS = os.environ.get("ENABLE_SCREENSHOTS", "true").lower() == "true"

ALLOWED_DATASET_EXTENSIONS = {".csv", ".tsv", ".txt"}


def ensure_storage() -> None:
    """Create the storage directories on startup."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)


def safe_path(relative_or_absolute: str, base: Path) -> Path:
    """Resolve a user-supplied path and guarantee it stays inside ``base``.

    Raises ``ValueError`` on traversal attempts (``../../etc/passwd``),
    absolute paths pointing elsewhere, or non-string input.
    """
    if not isinstance(relative_or_absolute, str) or not relative_or_absolute.strip():
        raise ValueError("path must be a non-empty string")
    candidate = Path(relative_or_absolute)
    resolved = (base / candidate).resolve() if not candidate.is_absolute() else candidate.resolve()
    if not resolved.is_relative_to(base.resolve()):
        raise ValueError(f"path escapes the allowed directory: {relative_or_absolute}")
    return resolved
