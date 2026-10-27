"""Health and dataset (inspection / preprocessing) endpoints."""

from __future__ import annotations

import hashlib
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict

import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import config
from app.preprocessing.inspector import profile_dataset, read_csv_profile
from app.preprocessing.pipeline import run_preprocessing
from app.schemas import InspectRequest, PreprocessRequest

router = APIRouter(prefix="/datasets", tags=["datasets"])

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


def _load(request_path: str) -> tuple[Path, pd.DataFrame]:
    try:
        path = config.safe_path(request_path, config.UPLOAD_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request_path}")
    if path.suffix.lower() not in config.ALLOWED_DATASET_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {path.suffix}")
    if path.stat().st_size > config.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the configured size limit.")
    try:
        df = read_csv_profile(path)
    except Exception as exc:  # pandas parser errors
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {exc}") from exc
    if df.empty:
        raise HTTPException(status_code=400, detail="The dataset contains no rows.")
    if len(df.columns) < 2:
        raise HTTPException(status_code=400, detail="The dataset must contain at least one feature column and one label column.")
    return path, df


@router.post("/inspect")
def inspect(req: InspectRequest) -> Dict[str, Any]:
    """STEP 2 - profile the raw dataset (types, missing values, duplicates, labels)."""
    started = time.perf_counter()
    _, df = _load(req.filePath)
    payload = profile_dataset(df, req.targetColumn, filename=Path(req.filePath).name)
    payload["elapsedMs"] = int((time.perf_counter() - started) * 1000)
    return payload


@router.post("/preprocess")
def preprocess(req: PreprocessRequest) -> Dict[str, Any]:
    """STEP 4 - run the real preprocessing pipeline and write a processed CSV."""
    started = time.perf_counter()
    path, df = _load(req.filePath)

    if req.targetColumn not in df.columns:
        raise HTTPException(
            status_code=400,
            detail=f"Target column '{req.targetColumn}' not found. Available: {list(df.columns)}",
        )

    options = req.options.model_dump()
    options["targetColumn"] = req.targetColumn

    try:
        result = run_preprocessing(df, options)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    out_name = req.outputFilename or f"{path.stem}__processed_{int(time.time())}.csv"
    if not _SAFE_NAME.match(out_name):
        raise HTTPException(status_code=400, detail="outputFilename contains unsupported characters.")
    if not out_name.endswith(".csv"):
        out_name += ".csv"

    try:
        out_path = config.safe_path(out_name, config.PROCESSED_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dataframe: pd.DataFrame = result.pop("dataframe")
    dataframe.to_csv(out_path, index=False)

    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    rel_path = str(out_path.relative_to(config.UPLOAD_DIR)).replace("\\", "/")

    return {
        "status": "COMPLETED",
        "sourceFile": path.name,
        "outputFile": rel_path,
        "outputFileName": out_name,
        "outputSizeBytes": out_path.stat().st_size,
        "outputSha256": digest,
        "elapsedMs": int((time.perf_counter() - started) * 1000),
        "columns": [str(c) for c in dataframe.columns],
        **result,
    }


@router.get("/processed/{file_name}")
def download_processed(file_name: str) -> FileResponse:
    """STEP 6 - download a processed CSV (also exposed through Spring Boot)."""
    try:
        path = config.safe_path(file_name, config.PROCESSED_DIR)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.exists():
        raise HTTPException(status_code=404, detail="Processed file not found.")
    return FileResponse(path, media_type="text/csv", filename=path.name)
