"""FastAPI entry point for the Python AI service."""

from __future__ import annotations

import os
import platform
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import config
from app.api.routes_datasets import router as datasets_router
from app.api.routes_scans import router as scans_router

APP_VERSION = "0.2.0"


@asynccontextmanager
async def lifespan(_: FastAPI):
    config.ensure_storage()
    yield


app = FastAPI(
    title="Multimodal Phishing Detection - AI Service",
    version=APP_VERSION,
    description=(
        "Provides dataset inspection/preprocessing and (from Phase 3) model inference. "
        "Spring Boot is the public API layer; this service is called by the backend."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets_router)
app.include_router(scans_router)


@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.get("/health", tags=["system"])
def health() -> Dict[str, Any]:
    """Liveness probe. Reports which optional model artifacts are present -
    it never fabricates model availability."""
    from app.inference import model_registry  # imported lazily: heavy deps load on demand

    return {
        "status": "UP",
        "service": "python-ai-service",
        "version": APP_VERSION,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "storage": {
            "uploadDir": str(config.UPLOAD_DIR),
            "processedDir": str(config.PROCESSED_DIR),
            "modelDir": str(config.MODEL_DIR),
        },
        "models": model_registry.status(),
    }


@app.get("/", tags=["system"])
def root() -> Dict[str, str]:
    return {"service": "python-ai-service", "docs": "/docs", "health": "/health"}
