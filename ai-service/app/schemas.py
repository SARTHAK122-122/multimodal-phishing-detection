"""Pydantic request/response models for the AI service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app import config


class InspectRequest(BaseModel):
    """STEP 2: profile an uploaded dataset."""
    filePath: str = Field(..., description="Path of the uploaded file, relative to UPLOAD_DIR")
    targetColumn: Optional[str] = Field(None, description="Column containing the label")


class PreprocessOptions(BaseModel):
    normalizeLabels: bool = True
    dropInvalidRows: bool = True
    convertTypes: bool = True
    detectConflictingDuplicates: bool = True
    removeDuplicates: bool = True
    handleMissing: bool = True
    missingStrategy: str = Field("median_mode", pattern="^(drop_rows|median_mode|drop_columns)$")
    missingMaxFraction: float = Field(0.5, ge=0.0, le=1.0)
    dedupeOnColumn: Optional[str] = None
    dropColumns: List[str] = Field(default_factory=list)
    selectColumns: List[str] = Field(default_factory=list)
    validateFeatures: bool = True
    labelMapping: Dict[str, str] = Field(default_factory=dict)


class PreprocessRequest(BaseModel):
    """STEP 4: execute the actual preprocessing."""
    filePath: str = Field(..., description="Path of the uploaded file, relative to UPLOAD_DIR")
    targetColumn: str = Field(..., min_length=1)
    options: PreprocessOptions = Field(default_factory=PreprocessOptions)
    outputFilename: Optional[str] = Field(None, description="Optional output name inside PROCESSED_DIR")


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    python: str
    storage: Dict[str, str]
    models: Dict[str, Any]


# ---- scan analysis requests (internal AI-service endpoints) ----

class WebsiteScanRequest(BaseModel):
    url: str = Field(..., min_length=4, max_length=2048,
                     description="The webpage URL to analyse (http/https).")
    fetch: bool = Field(True, description="Fetch the raw HTML (safe HTTP client).")
    render: bool = Field(True, description="Render in headless Chromium for screenshot/DOM.")
    maxFetchBytes: Optional[int] = Field(None, ge=1000, le=config.MAX_FETCH_BYTES)


class EmailScanRequest(BaseModel):
    subject: str = Field("", max_length=980)
    body: str = Field(..., min_length=1, max_length=100000)
    sender: str = Field("", max_length=320,
                        description="Optional From address/display name.")
    spf: str = Field("", max_length=40, description="Optional SPF result token.")
    dkim: str = Field("", max_length=40, description="Optional DKIM result token.")
    dmarc: str = Field("", max_length=40, description="Optional DMARC result token.")
    analyzeLinks: bool = Field(True, description="Analyse extracted links with the URL engine.")


class SmsScanRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    sender: str = Field("", max_length=64, description="Optional sender ID/number.")
    analyzeLinks: bool = Field(True, description="Analyse extracted links with the URL engine.")


class QrScanRequest(BaseModel):
    filePath: str = Field(..., description="Path of the uploaded QR image, relative to UPLOAD_DIR.")
