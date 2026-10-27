"""End-to-end EMAIL phishing analysis pipeline.

Combines three evidence sources and fuses them (weights: text 0.45, links 0.35,
sender/header 0.20):

1. **Text** - the shared social-engineering lexicon over subject + body, with
   exact phrase highlighting.
2. **Links** - every extracted link scored by the URL engine (string features
   only; links inside an email are NEVER visited).
3. **Sender & headers** - display-name vs address inconsistency, brand claims on
   unrelated domains, and SPF/DKIM/DMARC results when they are actually present.

Honesty rules
-------------
* SPF/DKIM/DMARC are only reported as passing when a ``pass`` result was
  supplied; an absent header is reported as "not available", never as "passed".
* Attachment names (when provided by the caller) are treated as metadata only;
  nothing is executed or opened.
"""

from __future__ import annotations

import json
import re
import time
from typing import Dict, List, Optional

from app.features import page_text
from app.features.links import analyze_links, extract_links
from app.findings import Finding
from app.ml import social_lexicon
from app.risk import engine, rulescores
from app.risk.engine import ModalityOutcome

# Free consumer email domains - fine for personal mail, but they cannot vouch
# for a brand that claims to be the sender.
_FREE_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "hotmail.com",
    "outlook.com", "live.com", "aol.com", "icloud.com", "mail.com", "proton.me",
    "protonmail.com", "zoho.com", "yandex.com", "gmx.com", "mail.ru",
}

_BRANDS = {
    "paypal": "paypal.com", "apple": "apple.com", "microsoft": "microsoft.com",
    "google": "google.com", "amazon": "amazon.com", "netflix": "netflix.com",
    "instagram": "instagram.com", "facebook": "facebook.com", "whatsapp": "whatsapp.com",
    "hdfc": "hdfcbank.com", "sbi": "sbi.co.in", "icici": "icicibank.com",
    "bank": "", "banking": "", "support": "", "security": "", "team": "",
}

_EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+\.[\w.-]+)")


def _json(obj) -> str:
    try:
        return json.dumps(obj, default=str)[:20000]
    except (TypeError, ValueError):
        return "{}"


def _label(score: Optional[float]) -> str:
    return engine.classify_score(score) if score is not None else engine.CLASS_UNKNOWN


def _split_sender(sender: str) -> tuple[str, str]:
    """Return (display_name, address) from 'Name <a@b.c>' or 'a@b.c'."""
    sender = (sender or "").strip()
    m = re.search(r"<([^>]+)>", sender)
    if m:
        addr = m.group(1).strip()
        display = sender[: m.start()].strip().strip('"')
        return display, addr
    if "@" in sender:
        return "", sender
    return sender, ""


def _analyze_sender(sender: str) -> tuple[float, List[Finding]]:
    """Rule-based sender risk in [0,1] plus findings."""
    findings: List[Finding] = []
    score = 0.0
    display, addr = _split_sender(sender)

    if not sender.strip():
        findings.append(Finding(
            modality="METADATA", evidence_type="no_sender_provided",
            description="No sender address was provided, so the sender could not be verified.",
            severity="INFO", direction="neutral"))
        return 0.0, findings

    domain = ""
    if addr:
        dm = _EMAIL_RE.search(addr)
        domain = (dm.group(1).lower() if dm else "")
        if not domain:
            # address present but unparsable
            findings.append(Finding(
                modality="METADATA", evidence_type="unparsable_sender",
                description="The sender address could not be parsed.",
                severity="LOW", supporting_value=addr[:120], direction="risk"))
            score += 0.1

    # Brand claimed in the display name but sent from an unrelated/free domain.
    display_l = display.lower()
    claimed = [b for b in _BRANDS if b in display_l and _BRANDS[b]]
    if claimed and domain:
        real = _BRANDS[claimed[0]]
        free = domain in _FREE_DOMAINS
        unrelated = not (domain == real or domain.endswith("." + real))
        if unrelated:
            sev = "HIGH" if free else "MEDIUM"
            findings.append(Finding(
                modality="METADATA", evidence_type="display_brand_address_mismatch",
                description=(f"The display name claims '{claimed[0].title()}' but the message "
                             f"comes from '{domain}', which is not {real}"
                             + (" (a free email provider)." if free else ".")),
                severity=sev, supporting_value=f"{display} <{addr}>"[:200], direction="risk"))
            score += 0.5 if free else 0.35

    return min(1.0, score), findings


def _analyze_auth(spf: str, dkim: str, dmarc: str) -> tuple[float, List[Finding]]:
    """Score authentication results. Distinguish present/pass/fail/none."""
    findings: List[Finding] = []
    score = 0.0
    for name, value in (("SPF", spf), ("DKIM", dkim), ("DMARC", dmarc)):
        v = (value or "").strip().lower()
        if not v:
            findings.append(Finding(
                modality="METADATA", evidence_type=f"{name.lower()}_not_available",
                description=f"No {name} result was available for this message; its "
                            "authentication could not be checked (this is NOT a pass).",
                severity="INFO", direction="neutral"))
            continue
        if v == "pass":
            findings.append(Finding(
                modality="METADATA", evidence_type=f"{name.lower()}_pass",
                description=f"{name} check passed.", severity="INFO", direction="safety"))
            score -= 0.05  # small legitimacy signal
        elif v in ("fail", "hardfail", "softfail", "none", "permerror", "temperror"):
            findings.append(Finding(
                modality="METADATA", evidence_type=f"{name.lower()}_{v}",
                description=f"{name} check returned '{v}', which does not authenticate the sender.",
                severity="MEDIUM", supporting_value=v, direction="risk"))
            score += 0.2
        else:
            findings.append(Finding(
                modality="METADATA", evidence_type=f"{name.lower()}_value",
                description=f"{name} returned an unrecognized value '{v}'.",
                severity="LOW", supporting_value=v[:40], direction="neutral"))
    return max(0.0, min(1.0, score)), findings


def analyze_email(payload: Dict) -> Dict:
    """Run the full email analysis. ``payload`` matches EmailScanRequest."""
    started = time.monotonic()
    subject = payload.get("subject") or ""
    body = payload.get("body") or ""
    sender = payload.get("sender") or ""
    analyze_links_flag = bool(payload.get("analyzeLinks", True))

    outcomes: List[ModalityOutcome] = []
    findings: List[Finding] = []

    # --- 1. NLP modality (subject + body lexicon) ---
    t0 = time.monotonic()
    subj_a = page_text.analyze_text(subject, source="subject") if subject.strip() else None
    body_a = page_text.analyze_text(body, source="body")
    combined = body_a
    if subj_a and subj_a.ok:
        # merge category scores (max) so a subject urgency adds to the body's
        combined.category_scores = social_lexicon.category_scores(
            (subj_a.phrase_matches if subj_a.ok else []) + body_a.phrase_matches)
        combined.phrase_matches = subj_a.phrase_matches + body_a.phrase_matches
        combined.highlighted = social_lexicon.highlight(
            (subject + " | " + body)[:20000], combined.phrase_matches)
    nlp_ms = int((time.monotonic() - t0) * 1000)
    if combined.ok:
        nlp_score = rulescores.score_text(combined)
        outcomes.append(ModalityOutcome(
            modality="NLP", status=engine.STATUS_OK, risk_score=nlp_score,
            prediction=_label(nlp_score), model_name="lexicon_rule_scorer",
            model_type="RULE_BASED", detail_json=_json(combined.as_evidence()),
            processing_time_ms=nlp_ms))
        findings.extend(combined.findings)
        if subj_a and subj_a.findings:
            for f in subj_a.findings:
                f.description = "[subject] " + f.description
            # subject findings already inside combined only if same matches; add distinct
    else:
        outcomes.append(ModalityOutcome(
            modality="NLP", status=engine.STATUS_FAILED, note=combined.detail))

    # --- 2. URL modality (extracted links, string-only) ---
    if analyze_links_flag:
        links = extract_links(subject + "\n" + body)
        la = analyze_links(links)
        if links:
            url_score = la.max_probability if la.max_probability is not None else 0.0
            outcomes.append(ModalityOutcome(
                modality="URL", status=engine.STATUS_OK, risk_score=url_score,
                prediction=_label(url_score), model_name="url_ensemble",
                model_type="ML",
                detail_json=_json({"links": la.per_link[:15],
                                   "note": "Links are scored on structure only; never visited."})))
            findings.extend(la.findings)
        else:
            outcomes.append(ModalityOutcome(
                modality="URL", status=engine.STATUS_SKIPPED,
                note="No links were present in the message."))
    else:
        outcomes.append(ModalityOutcome(
            modality="URL", status=engine.STATUS_SKIPPED, note="Link analysis disabled."))

    # --- 3. METADATA modality (sender + auth headers) ---
    sender_score, sender_findings = _analyze_sender(sender)
    auth_score, auth_findings = _analyze_auth(payload.get("spf", ""), payload.get("dkim", ""),
                                              payload.get("dmarc", ""))
    meta_score = min(1.0, max(sender_score, auth_score))
    findings.extend(sender_findings)
    findings.extend(auth_findings)
    outcomes.append(ModalityOutcome(
        modality="METADATA", status=engine.STATUS_OK, risk_score=meta_score,
        prediction=_label(meta_score), model_name="sender_header_rules",
        model_type="RULE_BASED",
        detail_json=_json({"sender": sender[:200], "spf": payload.get("spf", ""),
                           "dkim": payload.get("dkim", ""), "dmarc": payload.get("dmarc", "")})))

    # --- 4. fusion ---
    assessment = engine.assess_risk("EMAIL", outcomes, findings)
    elapsed_ms = int((time.monotonic() - started) * 1000)

    redacted_body = body[:2000]
    return {
        "inputType": "EMAIL",
        "submittedInput": f"{subject[:200]} | {redacted_body[:300]}",
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
        "extractedLinks": extract_links(subject + "\n" + body)[:15],
    }
