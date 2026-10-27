"""URL extraction from free text and safe (no-fetch) link risk analysis.

Used by the email, SMS and QR modalities. Critically, these links are analysed
on their **string features only** - the scanner never visits a link found inside
an email/message/QR, because following attacker-controlled links is exactly the
behaviour that gets a scanner phished or turned into a pivot. Validation still
runs (scheme/port/address checks) so a ``file://`` or internal link is reported
as unsafe without ever being opened.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.acquisition.url_safety import validate_url_for_fetch
from app.findings import Finding
from app.models import url_model
from app.risk import engine

# Loose but conservative URL matcher for text (email/SMS bodies).
_URL_RE = re.compile(
    r"(?i)\b(?:https?://|www\.)[^\s<>\"')\]]+"
)
# Trailing punctuation commonly glued to a URL in prose.
_TRAIL = ".,;:!?)]}\"'"


@dataclass
class LinkAnalysis:
    ok: bool = True
    detail: str = ""
    links: List[str] = field(default_factory=list)
    # Highest-risk link drives the URL sub-score for the modality.
    max_probability: Optional[float] = None
    max_probability_link: str = ""
    per_link: List[dict] = field(default_factory=list)
    findings: List[Finding] = field(default_factory=list)


def extract_links(text: str) -> List[str]:
    """Pull candidate URLs out of a free-text body, de-duplicated, bounded."""
    if not isinstance(text, str) or not text.strip():
        return []
    out: List[str] = []
    for m in _URL_RE.finditer(text):
        u = m.group(0).rstrip(_TRAIL)
        # Normalise a bare 'www.' to https so the engine can parse it.
        if u.lower().startswith("www."):
            u = "https://" + u
        if u not in out:
            out.append(u)
        if len(out) >= 25:
            break
    return out


def analyze_links(links: List[str]) -> LinkAnalysis:
    """Analyse extracted links with the URL engine (string features, no fetch)."""
    result = LinkAnalysis(links=links)
    if not links:
        result.detail = "No links were found in the text."
        return result

    best = -1.0
    for link in links:
        verdict = validate_url_for_fetch(link)
        pred = url_model.predict(link)
        proba = pred.probability if pred.ok else None
        entry = {
            "link": link[:500],
            "safeToFetch": verdict.safe,
            "validationReason": verdict.reason,
            "riskScore": round(proba, 4) if proba is not None else None,
            "modelsUsed": pred.models_used,
        }
        result.per_link.append(entry)

        if not verdict.safe:
            result.findings.append(Finding(
                modality="URL", evidence_type=f"link_unsafe_{verdict.reason}",
                description=f"A link points somewhere unsafe: {verdict.detail} ({link[:120]})",
                severity="MEDIUM", supporting_value=link[:200], direction="risk",
            ))
        if proba is not None and proba >= 0.6:
            result.findings.append(Finding(
                modality="URL", evidence_type="link_flagged_by_model",
                description=("The URL model scored a link in this message as likely phishing "
                             f"(P={proba:.2f}): {link[:120]}"),
                severity="HIGH" if proba >= 0.75 else "MEDIUM",
                supporting_value=link[:200], kind="INFERENCE", direction="risk",
            ))
            if len([f for f in result.findings if f.evidence_type == "link_flagged_by_model"]) == 1:
                result.findings.append(Finding(
                    modality="URL", evidence_type="link_shows_https_lookalike",
                    description=("Links inside messages are scored on structure only; the "
                                 "scanner does not visit them."),
                    severity="INFO", direction="neutral",
                ))
        if proba is not None and proba > best:
            best = proba
            result.max_probability_link = link

    result.max_probability = best if best >= 0 else None
    return result
