"""End-to-end SMS / suspicious-message analysis pipeline.

Fuses (weights: text 0.60, links 0.30, sender 0.10):

1. **Text** - the shared social-engineering lexicon with exact phrase
   highlighting (urgency, prize scams, bank/account warnings, OTP requests).
2. **Links** - extracted URLs scored by the URL engine (never visited).
3. **Sender** - optional sender ID/number; only reliable signals are used
   (premium-rate / suspicious short-code patterns), with an honest note that no
   authoritative malicious-number database is consulted.

Keyword matches alone never decide the verdict - text, link and sender evidence
are combined, and a message with no manipulated language scores low.
"""

from __future__ import annotations

import json
import re
import time
from typing import Dict, List, Optional

from app.features import page_text
from app.features.links import analyze_links, extract_links
from app.findings import Finding
from app.risk import engine, rulescores
from app.risk.engine import ModalityOutcome

# Premium-rate / suspicious number shapes (India-centric + generic). This is a
# syntactic heuristic, NOT a reputation feed - stated honestly in the finding.
_PREMIUM_RE = re.compile(r"^(?:\+?\d{1,3}[- ]?)?(?:1\d{3}|[6-9]\d{9})$")


def _json(obj) -> str:
    try:
        return json.dumps(obj, default=str)[:12000]
    except (TypeError, ValueError):
        return "{}"


def _label(score: Optional[float]) -> str:
    return engine.classify_score(score) if score is not None else engine.CLASS_UNKNOWN


def _analyze_sender(sender: str) -> tuple[float, List[Finding]]:
    findings: List[Finding] = []
    if not sender.strip():
        return 0.0, findings
    s = sender.strip()
    if _PREMIUM_RE.match(s):
        findings.append(Finding(
            modality="METADATA", evidence_type="sender_number_shape",
            description=(f"The sender '{s[:20]}' matches a premium-rate or short-code "
                         "pattern. This is a syntactic heuristic only, not a reputation "
                         "check."),
            severity="LOW", supporting_value=s[:20], direction="risk"))
        return 0.15, findings
    return 0.0, findings


def analyze_sms(payload: Dict) -> Dict:
    """Run the full SMS/message analysis. ``payload`` matches SmsScanRequest."""
    started = time.monotonic()
    message = payload.get("message") or ""
    sender = payload.get("sender") or ""
    analyze_links_flag = bool(payload.get("analyzeLinks", True))

    outcomes: List[ModalityOutcome] = []
    findings: List[Finding] = []

    # --- 1. NLP (lexicon) ---
    t0 = time.monotonic()
    text_a = page_text.analyze_text(message, source="message")
    nlp_ms = int((time.monotonic() - t0) * 1000)
    if text_a.ok:
        nlp_score = rulescores.score_text(text_a)
        outcomes.append(ModalityOutcome(
            modality="NLP", status=engine.STATUS_OK, risk_score=nlp_score,
            prediction=_label(nlp_score), model_name="lexicon_rule_scorer",
            model_type="RULE_BASED", detail_json=_json(text_a.as_evidence()),
            processing_time_ms=nlp_ms))
        findings.extend(text_a.findings)
    else:
        outcomes.append(ModalityOutcome(
            modality="NLP", status=engine.STATUS_FAILED, note=text_a.detail))

    # --- 2. URL (extracted links) ---
    if analyze_links_flag:
        links = extract_links(message)
        la = analyze_links(links)
        if links:
            url_score = la.max_probability if la.max_probability is not None else 0.0
            outcomes.append(ModalityOutcome(
                modality="URL", status=engine.STATUS_OK, risk_score=url_score,
                prediction=_label(url_score), model_name="url_ensemble", model_type="ML",
                detail_json=_json({"links": la.per_link[:10]})))
            findings.extend(la.findings)
        else:
            outcomes.append(ModalityOutcome(
                modality="URL", status=engine.STATUS_SKIPPED,
                note="No links were present in the message."))
    else:
        outcomes.append(ModalityOutcome(
            modality="URL", status=engine.STATUS_SKIPPED, note="Link analysis disabled."))

    # --- 3. METADATA (sender) ---
    meta_score, meta_findings = _analyze_sender(sender)
    findings.extend(meta_findings)
    outcomes.append(ModalityOutcome(
        modality="METADATA", status=engine.STATUS_OK, risk_score=meta_score,
        prediction=_label(meta_score), model_name="sender_rules", model_type="RULE_BASED",
        detail_json=_json({"sender": sender[:64]})))

    # --- 4. fusion ---
    assessment = engine.assess_risk("SMS", outcomes, findings)
    elapsed_ms = int((time.monotonic() - started) * 1000)

    return {
        "inputType": "SMS",
        "submittedInput": message[:1000],
        "normalizedInput": "",
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
        "extractedLinks": extract_links(message)[:10],
    }
