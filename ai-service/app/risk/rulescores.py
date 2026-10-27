"""Transparent rule-based scorers that map observations to a [0,1] risk score.

These are used for the modalities that do not (yet) have a trained model - the
DOM, the page/email/message text, and the forms/links analysis - so the platform
never pretends a black-box model produced a number it did not. Each scorer is a
documented, auditable formula over direct observations, and every signal it uses
is also emitted as a :class:`~app.findings.Finding` so the score is explainable.

When a trained model for a modality becomes available it replaces the rule scorer
for that modality; the risk engine does not care which produced the score.
"""

from __future__ import annotations

from typing import Dict, Iterable, List

from app.features.html_features import HtmlAnalysis
from app.features.page_text import TextAnalysis
from app.ml import social_lexicon

# --- text (NLP) scoring -----------------------------------------------------
# The strongest manipulative category dominates; extra categories add a small
# bounded bump. A page/email with no matched phrase scores ~0.
_TEXT_CATEGORY_WEIGHT: Dict[str, float] = {
    "credential_request": 0.95,
    "account_threat": 0.85,
    "financial": 0.8,
    "impersonation": 0.75,
    "urgency": 0.7,
    "secrecy": 0.6,
    "attachment": 0.5,
}
_MULTI_CATEGORY_BUMP = 0.05


def score_text(analysis: TextAnalysis) -> float:
    """[0,1] risk from lexicon category scores. 0 when nothing matched."""
    if not analysis.ok or not analysis.category_scores:
        return 0.0
    base = max(analysis.category_scores.values(), default=0.0)
    bump = _MULTI_CATEGORY_BUMP * max(0, len(analysis.category_scores) - 1)
    return round(min(1.0, base + bump), 4)


# --- HTML / DOM scoring -----------------------------------------------------
# Each signal is a documented weight; combined with noisy-OR so several
# independent suspicious traits push toward 1 without ever exceeding it.
_HTML_SIGNALS = {
    "brand_claim_with_external_form": 0.85,
    "password_form_external_action": 0.6,
    "external_form_action": 0.3,
    "insecure_form_submission": 0.25,
    "external_iframe": 0.2,
    "all_links_external": 0.25,
    "meta_refresh_redirect": 0.15,
    "password_form_get_method": 0.3,
    "many_external_scripts": 0.1,
}


def _noisy_or(weights: Iterable[float]) -> float:
    complement = 1.0
    for w in weights:
        complement *= (1.0 - min(1.0, max(0.0, w)))
    return round(1.0 - complement, 4)


def score_html(analysis: HtmlAnalysis) -> float:
    """[0,1] DOM risk from the rule signals that actually fired."""
    if not analysis.ok:
        return 0.0
    fired = [f.evidence_type for f in analysis.findings]
    weights = [_HTML_SIGNALS[t] for t in fired if t in _HTML_SIGNALS]
    if not weights:
        return 0.02  # a clean DOM carries a tiny neutral baseline, not 0
    return _noisy_or(weights)


# --- forms / links / redirects scoring --------------------------------------
def score_forms_links(analysis: HtmlAnalysis, redirect_count: int = 0) -> float:
    """[0,1] risk focused on data-exfiltration paths (forms, external links,
    redirects). Complements the DOM score without duplicating it."""
    if not analysis.ok:
        return 0.0
    parts: List[float] = []
    if analysis.features.get("form_action_external", 0) > 0:
        parts.append(0.4)
    if analysis.features.get("form_action_http_on_https", 0) > 0:
        parts.append(0.3)
    if analysis.features.get("num_password_forms", 0) > 0 and \
            analysis.features.get("form_action_external", 0) > 0:
        parts.append(0.4)  # credential exfiltration path
    if analysis.features.get("link_text_ratio_external", 0) >= 1.0 and \
            analysis.features.get("num_links", 0) >= 4:
        parts.append(0.2)
    if redirect_count >= 2:
        parts.append(0.2)
    elif redirect_count == 1:
        parts.append(0.08)
    if not parts:
        return 0.02
    return _noisy_or(parts)


def score_from_categories(category_scores: Dict[str, float]) -> float:
    """Standalone lexicon->score for pre-computed category maps (email/SMS)."""
    if not category_scores:
        return 0.0
    base = max(category_scores.values())
    bump = _MULTI_CATEGORY_BUMP * max(0, len(category_scores) - 1)
    return round(min(1.0, base + bump), 4)
