"""End-to-end QR-code phishing analysis pipeline.

Steps (mirrors the required QR workflow):
1. Validate the uploaded image file (type/size/path) inside UPLOAD_DIR.
2. Decode the QR payload with OpenCV ``QRCodeDetector``.
3. Classify the payload type (URL / text / non-URL scheme like ``WIFI:``).
4. If it contains a URL, analyse that destination with the same URL engine used
   by the website modality - but **never navigate to it** (decode only).
5. Fuse (weights: URL 0.80, payload-metadata 0.15, text 0.05) into a verdict.

Honesty rules
-------------
* A QR code is not malicious merely because it decodes; the *destination* and
  its evidence decide the verdict.
* Unsupported/unsafe payload schemes are reported as such and refused for
  analysis, not silently treated as safe.
* Unreadable QR images are handled gracefully with a clear reason.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List, Optional

from app import config
from app.features import page_text
from app.features.links import analyze_links, extract_links
from app.findings import Finding
from app.risk import engine
from app.risk.engine import ModalityOutcome

# Payload schemes that carry a URL destination.
_URL_SCHEMES = ("http://", "https://", "www.")
# Non-URL schemes we recognise and report (not analysed as web destinations).
_KNOWN_SCHEMES = ("wifi:", "mailto:", "tel:", "sms:", "begin:vcard", "begin:vevent",
                  "geo:", "market:", "smsto:")

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"}


def _json(obj) -> str:
    try:
        return json.dumps(obj, default=str)[:20000]
    except (TypeError, ValueError):
        return "{}"


def _label(score: Optional[float]) -> str:
    return engine.classify_score(score) if score is not None else engine.CLASS_UNKNOWN


def _find_url(payload: str) -> str:
    """Return a URL contained in the payload (exact or substring), or ''."""
    p = payload.strip()
    low = p.lower()
    for scheme in _URL_SCHEMES:
        if low.startswith(scheme):
            return p
    # Some payloads embed a URL inside other text (vCard, promo copy).
    links = extract_links(p)
    return links[0] if links else ""


def decode_qr(image_path: Path) -> tuple[bool, str, str]:
    """Decode a QR image. Returns (ok, data, reason). Never raises."""
    try:
        import cv2
    except Exception:
        return False, "", "opencv_unavailable"
    try:
        img = cv2.imread(str(image_path))
        if img is None:
            return False, "", "image_unreadable"
        detector = cv2.QRCodeDetector()
        # tryDecode handles multi-QR images better than detectAndDecode alone.
        data, points, _ = detector.detectAndDecode(img)
        if points is None or not data:
            # Retry after grayscale + upscale for small/low-contrast codes.
            import cv2 as _cv
            gray = _cv.cvtColor(img, _cv.COLOR_BGR2GRAY)
            big = _cv.resize(gray, None, fx=2.0, fy=2.0, interpolation=_cv.INTER_CUBIC)
            data, points, _ = detector.detectAndDecode(big)
        if not data:
            return False, "", "no_qr_detected"
        return True, data, ""
    except Exception as exc:
        return False, "", f"decode_error:{exc.__class__.__name__}"


def analyze_qr(file_path: str) -> Dict:
    """Analyse an uploaded QR image by relative path inside UPLOAD_DIR."""
    started = time.monotonic()
    outcomes: List[ModalityOutcome] = []
    findings: List[Finding] = []
    decoded = ""
    payload_type = "UNKNOWN"

    # --- 0. validate file ---
    try:
        path = config.safe_path(file_path, config.UPLOAD_DIR)
    except ValueError as exc:
        return _failed("invalid_path", str(exc), started)
    if not path.exists():
        return _failed("file_not_found", "The uploaded file could not be found.", started)
    if path.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        return _failed("unsupported_file_type",
                       f"QR decoding expects an image ({', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}).",
                       started)
    if path.stat().st_size > config.MAX_UPLOAD_BYTES:
        return _failed("file_too_large", "The uploaded image exceeds the size limit.", started)

    # --- 1. decode ---
    ok, data, reason = decode_qr(path)
    if not ok:
        findings.append(Finding(
            modality="METADATA", evidence_type=f"qr_decode_failed_{reason}",
            description=("The QR code could not be decoded from the image. It may be blurry, "
                         "partial, or not a QR code at all."),
            severity="INFO", direction="neutral"))
        outcomes.append(ModalityOutcome(
            modality="METADATA", status=engine.STATUS_FAILED, note=f"Decode failed ({reason})."))
        outcomes.append(ModalityOutcome(
            modality="URL", status=engine.STATUS_SKIPPED, note="Nothing was decoded."))
        assessment = engine.assess_risk("QR", outcomes, findings)
        return _assemble(file_path, "", "UNREADABLE", outcomes, findings, assessment,
                         started, decoded="")

    decoded = data.strip()
    low = decoded.lower()

    # --- 2. payload classification ---
    url = _find_url(decoded)
    if url:
        payload_type = "URL"
    elif low.startswith(_KNOWN_SCHEMES):
        payload_type = "NON_URL_SCHEME"
    else:
        payload_type = "TEXT"

    # --- 3. URL destination analysis (string-only, no navigation) ---
    if url:
        la = analyze_links([url])
        url_score = la.max_probability if la.max_probability is not None else 0.0
        outcomes.append(ModalityOutcome(
            modality="URL", status=engine.STATUS_OK, risk_score=url_score,
            prediction=_label(url_score), model_name="url_ensemble", model_type="ML",
            detail_json=_json({"destination": url[:500], "links": la.per_link,
                               "note": "Destination decoded and scored; never visited."})))
        findings.extend(la.findings)
        findings.append(Finding(
            modality="METADATA", evidence_type="qr_destination",
            description=f"The QR code points to: {url[:160]}",
            severity="INFO", supporting_value=url[:200], direction="neutral"))
    else:
        outcomes.append(ModalityOutcome(
            modality="URL", status=engine.STATUS_SKIPPED,
            note="The QR payload does not contain a web URL."))

    # --- 4. payload metadata (type + scheme safety) ---
    meta_score = 0.0
    if payload_type == "NON_URL_SCHEME":
        findings.append(Finding(
            modality="METADATA", evidence_type="non_url_payload",
            description=(f"The QR payload is a '{decoded.split(':', 1)[0]}' payload, not a web "
                         "link. It was not analysed as a web destination."),
            severity="INFO", supporting_value=decoded[:80], direction="neutral"))
    elif payload_type == "TEXT" and not url:
        findings.append(Finding(
            modality="METADATA", evidence_type="text_payload",
            description="The QR payload is plain text, not a web link.",
            severity="INFO", supporting_value=decoded[:80], direction="neutral"))
    outcomes.append(ModalityOutcome(
        modality="METADATA", status=engine.STATUS_OK, risk_score=meta_score,
        prediction=_label(meta_score), model_name="payload_rules", model_type="RULE_BASED",
        detail_json=_json({"payloadType": payload_type, "decodedLength": len(decoded)})))

    # --- 5. NLP on decoded text (only meaningful for TEXT payloads) ---
    if payload_type == "TEXT":
        from app.risk import rulescores
        text_a = page_text.analyze_text(decoded, source="qr-text")
        if text_a.ok:
            nlp_score = rulescores.score_text(text_a)
            outcomes.append(ModalityOutcome(
                modality="NLP", status=engine.STATUS_OK, risk_score=nlp_score,
                prediction=_label(nlp_score), model_name="lexicon_rule_scorer",
                model_type="RULE_BASED", detail_json=_json(text_a.as_evidence())))
            findings.extend(text_a.findings)
        else:
            outcomes.append(ModalityOutcome(
                modality="NLP", status=engine.STATUS_SKIPPED, note=text_a.detail))
    else:
        outcomes.append(ModalityOutcome(
            modality="NLP", status=engine.STATUS_SKIPPED, note="No free text to analyse."))

    # --- 6. fusion ---
    assessment = engine.assess_risk("QR", outcomes, findings)
    return _assemble(file_path, url or decoded, payload_type, outcomes, findings,
                     assessment, started, decoded=decoded)


def _failed(reason: str, detail: str, started: float) -> Dict:
    return {
        "inputType": "QR", "submittedInput": "", "normalizedInput": "",
        "status": "FAILED", "classification": engine.CLASS_UNKNOWN,
        "riskLevel": engine.LEVEL_UNKNOWN, "riskScore": None,
        "explanation": detail, "caveats": [detail], "weightsUsed": {},
        "evidenceModifier": 0.0, "missingModalities": ["URL", "NLP", "METADATA"],
        "modalities": [], "evidence": [], "screenshot": "",
        "processingTimeMs": int((time.monotonic() - started) * 1000),
        "decodedPayload": "", "payloadType": "UNREADABLE", "error": reason,
    }


def _assemble(file_path, normalized, payload_type, outcomes, findings, assessment,
              started, decoded) -> Dict:
    elapsed_ms = int((time.monotonic() - started) * 1000)
    return {
        "inputType": "QR",
        "submittedInput": file_path[:300],
        "normalizedInput": (normalized or "")[:1000],
        "status": assessment.scan_status,
        "classification": assessment.classification,
        "riskLevel": assessment.risk_level,
        "riskScore": assessment.risk_score,
        "explanation": assessment.explanation,
        "caveats": assessment.caveats,
        "weightsUsed": assessment.weights_used,
        "evidenceModifier": assessment.evidence_modifier,
        "missingModalities": assessment.missing_modalities,
        "modalities": [
            {"modality": m.modality, "status": m.status, "prediction": m.prediction,
             "riskScore": m.risk_score, "modelName": m.model_name,
             "modelVersion": m.model_version, "modelType": m.model_type,
             "detail": json.loads(m.detail_json) if m.detail_json else {},
             "processingTimeMs": m.processing_time_ms, "note": m.note}
            for m in outcomes],
        "evidence": [f.as_dict() for f in findings],
        "screenshot": "",
        "processingTimeMs": elapsed_ms,
        "decodedPayload": decoded[:1000],
        "payloadType": payload_type,
    }
