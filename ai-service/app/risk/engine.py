"""Risk engine: multimodal fusion, classification and risk-level assignment.

This is the single, shared decision layer for **all** input categories. Website,
email, SMS and QR pipelines each produce a list of :class:`ModalityOutcome`s
plus raw :class:`Finding`s and hand them to :func:`assess_risk`. The engine is
pure (no I/O, no model loading) so its behaviour is fully unit-testable and its
thresholds are auditable in one place.

Fusion method (transparent baseline)
-----------------------------------
A weighted mean over the modalities that are actually available:

    fused = Σ(w_i · score_i) / Σ(w_i)   for available i only

When a modality is missing (failed fetch, absent model, unsupported payload)
its weight is simply excluded and the rest renormalise - a missing screenshot
NEVER silently means "low risk". The weights below are a documented starting
point, not a learned optimum; they are reported verbatim in every result.

Evidence modifier
-----------------
Model scores are nudged by direct observations, bounded so rules cannot
overwhelm the models:
    +0.10 per CRITICAL risk finding, +0.05 per HIGH, capped at +0.25
    -0.05 per "safety" finding, capped at -0.10
A single CRITICAL finding also sets a **floor** - the verdict can never come
back cleaner than SUSPICIOUS/HIGH no matter what the models say.

Score semantics
---------------
The fused value is a **model score in [0,1]**, NOT a calibrated probability.
It is reported as ``riskScore`` only alongside this caveat everywhere it is
surfaced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.findings import Finding, severity_rank

# --- classification / risk vocabularies (shared across modalities) ---
CLASS_LEGITIMATE = "LEGITIMATE"
CLASS_SUSPICIOUS = "SUSPICIOUS"
CLASS_PHISHING = "PHISHING"
CLASS_UNKNOWN = "UNKNOWN"

LEVEL_LOW = "LOW"
LEVEL_MEDIUM = "MEDIUM"
LEVEL_HIGH = "HIGH"
LEVEL_CRITICAL = "CRITICAL"
LEVEL_UNKNOWN = "UNKNOWN"

# Modality statuses
STATUS_OK = "OK"
STATUS_SKIPPED = "SKIPPED"
STATUS_FAILED = "FAILED"
STATUS_MODEL_MISSING = "MODEL_MISSING"

# --- documented score -> (classification, risk level) ladder ---
# Ordered high-to-low; first matching band wins.
THRESHOLDS: List[Tuple[float, str, str]] = [
    (0.75, CLASS_PHISHING, LEVEL_CRITICAL),
    (0.60, CLASS_PHISHING, LEVEL_HIGH),
    (0.40, CLASS_SUSPICIOUS, LEVEL_MEDIUM),
    (0.25, CLASS_SUSPICIOUS, LEVEL_LOW),
    (0.0,  CLASS_LEGITIMATE, LEVEL_LOW),
]

# Evidence-modifier bounds and per-severity increments.
EVIDENCE_BONUS_BY_SEVERITY = {4: 0.10, 3: 0.05}   # CRITICAL, HIGH  (rank -> increment)
EVIDENCE_BONUS_CAP = 0.25
EVIDENCE_PENALTY_PER_SAFETY = 0.05                # legitimacy signals
EVIDENCE_PENALTY_CAP = 0.10

# Default fusion weights per input category. Renormalised over available
# modalities at assessment time.
FUSION_WEIGHTS: Dict[str, Dict[str, float]] = {
    "WEBSITE": {
        # Content modalities carry more weight than the URL string alone: the
        # project's core finding is that URL-only detection both over-fires on
        # short high-entropy domains and misses clean-looking phishing pages.
        # URL is kept meaningful (not zero) so an unresolvable/obvious phishing
        # host is still caught on its own.
        "URL": 0.18, "HTML": 0.26, "NLP": 0.20, "VISION": 0.18, "FORM_LINK": 0.18,
    },
    "EMAIL": {
        "NLP": 0.45, "URL": 0.35, "METADATA": 0.20,
    },
    "SMS": {
        "NLP": 0.60, "URL": 0.30, "METADATA": 0.10,
    },
    "QR": {
        "URL": 0.80, "METADATA": 0.15, "NLP": 0.05,
    },
}


@dataclass
class ModalityOutcome:
    """One modality's contribution to a scan."""

    modality: str                 # URL | HTML | NLP | VISION | FORM_LINK | METADATA | FUSION
    status: str = STATUS_OK       # OK | SKIPPED | FAILED | MODEL_MISSING
    risk_score: Optional[float] = None   # 0..1, None when not computable
    prediction: Optional[str] = None     # LEGITIMATE | SUSPICIOUS | PHISHING (optional)
    model_name: str = ""
    model_version: str = ""
    model_type: str = ""          # ML | DL | RULE_BASED
    detail_json: str = "{}"
    processing_time_ms: int = 0
    findings: List[Finding] = field(default_factory=list)
    note: str = ""                # human explanation of why it was skipped/failed

    @property
    def available(self) -> bool:
        return self.status == STATUS_OK and self.risk_score is not None


@dataclass
class RiskAssessment:
    classification: str
    risk_level: str
    risk_score: Optional[float]
    fused_from: List[str] = field(default_factory=list)
    missing_modalities: List[str] = field(default_factory=list)
    weights_used: Dict[str, float] = field(default_factory=dict)
    evidence_modifier: float = 0.0
    evidence_floor_applied: bool = False
    explanation: str = ""
    scan_status: str = "COMPLETED"   # COMPLETED | PARTIAL | FAILED
    caveats: List[str] = field(default_factory=list)


def _classify(score: float) -> Tuple[str, str]:
    for cut, cls, level in THRESHOLDS:
        if score >= cut:
            return cls, level
    return CLASS_LEGITIMATE, LEVEL_LOW


def classify_score(score: float) -> str:
    """Map a single [0,1] modality score to a classification label."""
    return _classify(max(0.0, min(1.0, float(score))))[0]


def assess_risk(
    input_type: str,
    modalities: List[ModalityOutcome],
    findings: Optional[List[Finding]] = None,
) -> RiskAssessment:
    """Fuse modality scores + findings into a final verdict. Pure function.

    ``input_type`` selects the weight profile (WEBSITE/EMAIL/SMS/QR). Unknown
    types fall back to an equal-weight profile so a new modality still works.
    """
    findings = findings or []
    weights = FUSION_WEIGHTS.get(input_type, {})
    if not weights:
        weights = {m.modality: 1.0 for m in modalities}

    available = [m for m in modalities if m.available]
    missing = [m.modality for m in modalities if not m.available]

    caveats: List[str] = []
    if not available:
        # Nothing to score at all - be explicit, never guess.
        return RiskAssessment(
            classification=CLASS_UNKNOWN,
            risk_level=LEVEL_UNKNOWN,
            risk_score=None,
            missing_modalities=missing,
            explanation="No modality could be scored (all analyses failed or their models "
                        "are unavailable), so no verdict is issued.",
            scan_status="FAILED",
            caveats=["No scored modality - result is UNKNOWN, not 'safe'."],
        )

    # --- weighted fusion, renormalised over AVAILABLE modalities only ---
    used: Dict[str, float] = {}
    numerator = 0.0
    denominator = 0.0
    for m in available:
        w = weights.get(m.modality, 0.1)
        used[m.modality] = w
        numerator += w * float(m.risk_score)
        denominator += w
    fused = numerator / denominator if denominator > 0 else 0.5

    # --- bounded evidence modifier ---
    bonus = 0.0
    penalty = 0.0
    for f in findings:
        rank = severity_rank(f.severity)
        if f.direction == "risk" and rank in EVIDENCE_BONUS_BY_SEVERITY:
            bonus += EVIDENCE_BONUS_BY_SEVERITY[rank]
        elif f.direction == "safety":
            penalty += EVIDENCE_PENALTY_PER_SAFETY
    bonus = min(bonus, EVIDENCE_BONUS_CAP)
    penalty = min(penalty, EVIDENCE_PENALTY_CAP)
    modifier = round(bonus - penalty, 4)
    adjusted = min(1.0, max(0.0, fused + modifier))

    classification, risk_level = _classify(adjusted)

    # --- critical-finding floor: strong direct evidence cannot be outvoted ---
    floor_applied = False
    if any(severity_rank(f.severity) >= 4 and f.direction == "risk" for f in findings):
        if classification == CLASS_LEGITIMATE or (
            classification == CLASS_SUSPICIOUS and risk_level == LEVEL_LOW
        ):
            classification, risk_level = CLASS_SUSPICIOUS, LEVEL_HIGH
            floor_applied = True
            caveats.append(
                "A CRITICAL direct observation was found; the verdict was raised to at "
                "least SUSPICIOUS/HIGH regardless of the model scores."
            )

    scan_status = "COMPLETED" if not missing else "PARTIAL"
    if missing:
        caveats.append(
            "Some modalities were unavailable (" + ", ".join(sorted(set(missing))) +
            "); the verdict reflects only the analyses that ran. An incomplete scan is "
            "not the same as a clean scan."
        )
    caveats.append(
        "riskScore is a fused model score in [0,1], not a calibrated probability."
    )

    parts = [f"Fused {len(available)} modality score(s) "
             f"({', '.join(sorted(used))}) with weights "
             + ", ".join(f"{k}={v:.2f}" for k, v in sorted(used.items())) + "."]
    if modifier:
        parts.append(f"Applied an evidence modifier of {modifier:+.2f} "
                     f"(bounded risk findings {bonus:+.2f}, legitimacy signals {penalty:+.2f}).")
    parts.append(f"Score {adjusted:.3f} falls in the "
                 f"[{classification}] band ({risk_level} risk).")

    return RiskAssessment(
        classification=classification,
        risk_level=risk_level,
        risk_score=round(adjusted, 4),
        fused_from=sorted(used),
        missing_modalities=sorted(set(missing)),
        weights_used={k: round(v, 3) for k, v in sorted(used.items())},
        evidence_modifier=modifier,
        evidence_floor_applied=floor_applied,
        explanation=" ".join(parts),
        scan_status=scan_status,
        caveats=caveats,
    )
