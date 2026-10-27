"""Internal analysis endpoints called by Spring Boot.

These are the AI-service side of the scan pipeline. They are "internal" in the
sense that the public API is Spring Boot (which owns auth, persistence and the
audit trail); this service binds to ``127.0.0.1`` by default so it is not
network-exposed. For defence-in-depth, if ``AI_SERVICE_API_KEY`` is set in the
environment, every request here must carry it in ``X-AI-Service-Key``.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, Depends, Header, HTTPException

from app.schemas import (
    EmailScanRequest,
    QrScanRequest,
    SmsScanRequest,
    WebsiteScanRequest,
)

router = APIRouter(prefix="/analyze", tags=["analyze"])


async def require_internal_key(x_ai_service_key: str = Header(default="")) -> None:
    """Optional shared-secret guard. Enforced only when configured."""
    expected = os.environ.get("AI_SERVICE_API_KEY", "")
    if expected and x_ai_service_key != expected:
        raise HTTPException(status_code=401, detail="Invalid or missing AI service key.")


@router.post("/website", response_model=None)
def analyze_website_endpoint(payload: WebsiteScanRequest,
                             _: None = Depends(require_internal_key)) -> Dict[str, Any]:
    """Full multimodal website analysis (URL + HTML + text + screenshot)."""
    from app.pipelines.website import analyze_website  # deferred: heavy deps

    return analyze_website(
        payload.url,
        fetch=payload.fetch,
        render=payload.render,
        max_fetch_bytes=payload.maxFetchBytes,
    )


@router.post("/email", response_model=None)
def analyze_email_endpoint(payload: EmailScanRequest,
                           _: None = Depends(require_internal_key)) -> Dict[str, Any]:
    from app.pipelines.email import analyze_email  # deferred

    return analyze_email(payload.model_dump())


@router.post("/sms", response_model=None)
def analyze_sms_endpoint(payload: SmsScanRequest,
                         _: None = Depends(require_internal_key)) -> Dict[str, Any]:
    from app.pipelines.sms import analyze_sms  # deferred

    return analyze_sms(payload.model_dump())


@router.post("/qr", response_model=None)
def analyze_qr_endpoint(payload: QrScanRequest,
                        _: None = Depends(require_internal_key)) -> Dict[str, Any]:
    from app.pipelines.qr import analyze_qr  # deferred

    return analyze_qr(payload.filePath)
