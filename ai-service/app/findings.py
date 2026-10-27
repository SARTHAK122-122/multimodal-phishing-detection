"""Shared, modality-agnostic finding (evidence) type.

Every analysis branch - URL, HTML/DOM, page text, vision, email, SMS, QR -
produces :class:`Finding` objects. They are the *raw observations* that flow
into the risk engine and are persisted as ``evidence`` rows.

Keeping one type across modalities is what lets the platform present a single,
consistent "why" section no matter which input category the user submitted.
It also keeps a hard line between **observation** (``FINDING``, directly
measured from the input) and **model inference** (``INFERENCE``, produced by a
classifier) - see :attr:`Finding.kind`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

# Severity is ordinal; the risk engine uses it to weight findings.
SEVERITY_ORDER = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

# kind: FINDING = direct observation of the input; INFERENCE = model output.
KIND_FINDING = "FINDING"
KIND_INFERENCE = "INFERENCE"


@dataclass
class Finding:
    """One piece of evidence supporting (or against) a risk verdict."""

    modality: str                 # URL | HTML | NLP | VISION | FORM_LINK | METADATA | FUSION | ...
    evidence_type: str            # stable machine token, e.g. "password_field"
    description: str              # human-readable sentence shown in the UI
    severity: str = "INFO"        # INFO | LOW | MEDIUM | HIGH | CRITICAL
    supporting_value: str = ""    # the concrete value observed (a URL, a count, a phrase)
    kind: str = KIND_FINDING
    # Direction of the signal. "risk" pushes toward phishing, "safety" pulls
    # toward legitimate, "neutral" is informational context only.
    direction: str = "risk"
    meta: Dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "modality": self.modality,
            "evidenceType": self.evidence_type,
            "description": self.description,
            "severity": self.severity,
            "supportingValue": self.supporting_value,
            "kind": self.kind,
            "direction": self.direction,
            "meta": self.meta,
        }

    @staticmethod
    def normalize_severity(value: Optional[str]) -> str:
        value = (value or "INFO").upper()
        return value if value in SEVERITY_ORDER else "INFO"


def severity_rank(value: Optional[str]) -> int:
    return SEVERITY_ORDER.get(Finding.normalize_severity(value), 0)
