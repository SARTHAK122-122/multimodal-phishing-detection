"""Webpage visible-text extraction and NLP analysis (the "page text" modality).

Produces a lexicon/rule-based analysis of the *visible* text of a page. The
matched phrases are returned with exact character spans so the UI can highlight
them, and category scores are returned for the risk engine.

Deep-learning NLP (DistilBERT) is designed to slot in behind this module, but a
transformer is only reported as available when its artifact is actually present
and a labelled dataset justified its training. Until then the modality honestly
reports a rule-based baseline rather than pretending to be a neural model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

from bs4 import BeautifulSoup

from app.findings import Finding
from app.ml import social_lexicon

# Fixed numeric schema for the NLP modality (usable to train a text model later).
FEATURE_NAMES: List[str] = [
    "text_length",
    "word_count",
    "avg_word_length",
    "num_unique_words",
    "lexical_diversity",
    "exclamation_count",
    "question_count",
    "all_caps_word_count",
    "digit_count",
    "num_categories_fired",
    "max_category_weight",
    "credential_score",
    "account_threat_score",
    "urgency_score",
    "financial_score",
    "secrecy_score",
    "impersonation_score",
    "attachment_score",
    "has_credential_request",
    "has_urgency",
]


@dataclass
class TextAnalysis:
    ok: bool = True
    detail: str = ""
    text: str = ""
    truncated: bool = False
    features: Dict[str, float] = field(default_factory=dict)
    phrase_matches: List[social_lexicon.PhraseMatch] = field(default_factory=list)
    category_scores: Dict[str, float] = field(default_factory=dict)
    highlighted: str = ""
    findings: List[Finding] = field(default_factory=list)

    def as_evidence(self) -> dict:
        return {
            "ok": self.ok,
            "detail": self.detail,
            "textLength": len(self.text),
            "truncated": self.truncated,
            "categoryScores": {k: round(v, 3) for k, v in self.category_scores.items()},
            "highlighted": self.highlighted,
            "matchedPhrases": [
                {"category": m.category, "phrase": m.phrase, "weight": m.weight}
                for m in self.phrase_matches[:40]
            ],
        }


# Tags whose text is never "visible content".
_STRIP_TAGS = {"script", "style", "noscript", "template", "svg", "head", "iframe"}
# Visible text cap; beyond this the page is marketing boilerplate.
MAX_TEXT_CHARS = 20000


def extract_visible_text(html: str) -> str:
    """Extract only the text a user would actually see, collapsing whitespace."""
    if not isinstance(html, str) or not html.strip():
        return ""
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        soup = BeautifulSoup(html, "html.parser")
    for tag in soup(_STRIP_TAGS):
        tag.decompose()
    # Remove hidden-by-attribute elements (display:none, hidden).
    for tag in soup.find_all(attrs={"style": re.compile(r"display\s*:\s*none", re.I)}):
        tag.decompose()
    for tag in soup.find_all(hidden=True):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", text).strip()


def analyze_text(text: str, *, source: str = "webpage") -> TextAnalysis:
    """Analyse a block of visible text with the shared lexicon. Never raises."""
    result = TextAnalysis()
    if not isinstance(text, str) or not text.strip():
        result.ok = False
        result.detail = "No visible text could be extracted from the page."
        result.features = {name: 0.0 for name in FEATURE_NAMES}
        return result

    truncated = len(text) > MAX_TEXT_CHARS
    work = text[:MAX_TEXT_CHARS]
    result.text = work
    result.truncated = truncated

    matches = social_lexicon.find_phrases(work)
    result.phrase_matches = matches
    result.category_scores = social_lexicon.category_scores(matches)
    result.highlighted = social_lexicon.highlight(work, matches)

    words = re.findall(r"[A-Za-z']+", work)
    word_count = len(words)
    unique = len({w.lower() for w in words})
    feats = result.features
    feats["text_length"] = float(len(work))
    feats["word_count"] = float(word_count)
    feats["avg_word_length"] = (sum(len(w) for w in words) / word_count) if word_count else 0.0
    feats["num_unique_words"] = float(unique)
    feats["lexical_diversity"] = (unique / word_count) if word_count else 0.0
    feats["exclamation_count"] = float(work.count("!"))
    feats["question_count"] = float(work.count("?"))
    feats["all_caps_word_count"] = float(sum(1 for w in words if len(w) >= 4 and w.isupper()))
    feats["digit_count"] = float(sum(c.isdigit() for c in work))

    for category in social_lexicon.CATEGORIES:
        feats[f"{category}_score"] = float(result.category_scores.get(category, 0.0))
    feats["num_categories_fired"] = float(len(result.category_scores))
    feats["max_category_weight"] = float(max(result.category_scores.values(), default=0.0))
    feats["has_credential_request"] = 1.0 if "credential_request" in result.category_scores else 0.0
    feats["has_urgency"] = 1.0 if "urgency" in result.category_scores else 0.0

    # Turn the strongest signals into explicit findings (for the evidence list).
    severity_by_category = {
        "credential_request": "HIGH",
        "account_threat": "HIGH",
        "financial": "MEDIUM",
        "impersonation": "MEDIUM",
        "urgency": "MEDIUM",
        "secrecy": "LOW",
        "attachment": "LOW",
    }
    for category, score in sorted(result.category_scores.items(), key=lambda kv: -kv[1]):
        phrases = [m.phrase for m in matches if m.category == category][:5]
        result.findings.append(Finding(
            modality="NLP",
            evidence_type=f"manipulative_language_{category}",
            description=(
                f"Text contains {len([m for m in matches if m.category == category])} "
                f"'{category.replace('_', ' ')}' phrase(s), e.g. "
                + ", ".join(f'"{p}"' for p in phrases[:3]) + "."
            ),
            severity=severity_by_category.get(category, "LOW"),
            supporting_value="; ".join(phrases)[:300],
            direction="risk",
        ))

    if result.category_scores.get("credential_request", 0) >= 0.9:
        result.findings.insert(0, Finding(
            modality="NLP", evidence_type="direct_credential_request",
            description=f"The {source} explicitly asks the reader to provide a password, OTP "
                        "or payment credential. Legitimate services do not ask for these by "
                        "message.",
            severity="CRITICAL", supporting_value=work[:200], direction="risk",
        ))

    return result
