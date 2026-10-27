"""Shared social-engineering lexicon.

One phrase database drives the webpage-NLP, email and SMS modalities so the
platform applies a single, consistent notion of "manipulative language". Each
category maps to a weight the risk engine can aggregate, and every matched
phrase is returned so the UI can **highlight the exact words** that triggered
the signal - the evidence must be inspectable, not just counted.

This is a transparent, auditable rule base. It is deliberately not a black-box
classifier: a reviewer can read every phrase that can ever fire. Text models
(DistilBERT) may be added alongside it, but the lexicon remains the explainable
backbone and the fallback when a transformer is unavailable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

# category -> (weight, [phrases])
# Weights: CRITICAL-ish categories score highest. Phrases are matched
# case-insensitively as word-ish substrings.
CATEGORIES: Dict[str, Tuple[float, List[str]]] = {
    "credential_request": (0.95, [
        "verify your account", "confirm your identity", "enter your password",
        "input your password", "type your password", "provide your password",
        "share your password", "login credentials", "log in credentials",
        "account credentials", "verify your password", "update your payment",
        "update your billing", "re-enter your password", "reenter your password",
        "social security number", "credit card number", "card number",
        "cvv", "atm pin", "otp", "one-time password", "one time password",
        "mother's maiden name", "bank account number", "account number",
    ]),
    "account_threat": (0.85, [
        "account will be suspended", "account has been suspended",
        "account suspended", "account will be closed", "account deactivated",
        "account will be deleted", "account will be locked", "account locked",
        "unauthorized access", "unusual sign-in", "unusual activity",
        "suspicious activity", "security alert", "your account has been",
        "confirm your account", "reactivate your account", "unlock your account",
        "legal action", "lawsuit", "criminal charges", "account termination",
    ]),
    "urgency": (0.7, [
        "act now", "act immediately", "immediately", "urgent", "within 24 hours",
        "within 12 hours", "within 48 hours", "expires today", "expires soon",
        "limited time", "hurry", "don't delay", "do not delay", "final notice",
        "last chance", "before it's too late", "before it is too late",
        "time is running out", "suspend your account", "expires in",
    ]),
    "financial": (0.8, [
        "wire transfer", "bank transfer", "western union", "moneygram",
        "bitcoin", "btc", "crypto", "gift card", "itunes card", "google play card",
        "paypal", "refund", "invoice", "payment required", "unpaid invoice",
        "overdue payment", "pending payment", "payment failed", "tax refund",
        "lottery", "jackpot", "inheritance", "prize", "you have won",
        "you've won", "winner", "congratulations you", "cash prize",
        "claim your prize", "claim your reward", "reward", "bonus",
    ]),
    "secrecy": (0.6, [
        "keep this confidential", "keep this secret", "keep this between you and me",
        "keep this strictly confidential", "do not tell anyone", "tell no one",
        "do not inform anyone", "this is strictly confidential",
        "do not mention this to", "do not reveal this",
    ]),
    "impersonation": (0.75, [
        "customer service", "support team", "security team", "it department",
        "administrator", "official notice", "from the desk of", "dear customer",
        "dear user", "dear valued", "dear sir", "dear madam", "attention please",
        "verified by", "microsoft team", "apple support", "google support",
        "paypal team", "netflix team", "bank team",
    ]),
    "attachment": (0.5, [
        "open the attachment", "see attached", "attached file", "find attached",
        "review the attachment", "download the attachment", "see the attached",
    ]),
}

# Pre-compiled patterns: (category, weight, regex)
_PATTERNS: List[Tuple[str, float, "re.Pattern[str]"]] = []


def _build_patterns() -> None:
    if _PATTERNS:
        return
    for category, (weight, phrases) in CATEGORIES.items():
        for phrase in phrases:
            escaped = re.escape(phrase)
            # Word-boundary-ish match; allow 's contraction tails to still hit.
            rx = re.compile(r"(?<![a-z])" + escaped + r"(?![a-z])", re.IGNORECASE)
            _PATTERNS.append((category, weight, rx))


# Single "any otp / any card" style loose patterns for highlighting density.
_LOOSE: List[Tuple[str, float, "re.Pattern[str]"]] = [
    ("credential_request", 0.6, re.compile(r"\b\d{4,8}\b(?=\s*(otp|code|pin))", re.IGNORECASE)),
    ("credential_request", 0.6, re.compile(r"\b(otp|pin|cvv|ssn)\b", re.IGNORECASE)),
    ("financial", 0.5, re.compile(r"\b(gift|steam|google|apple|amazon)\s*card\b", re.IGNORECASE)),
]


@dataclass
class PhraseMatch:
    category: str
    phrase: str
    weight: float
    start: int
    end: int

    def as_dict(self) -> dict:
        return {
            "category": self.category,
            "phrase": self.phrase,
            "weight": self.weight,
            "start": self.start,
            "end": self.end,
        }


def find_phrases(text: str) -> List[PhraseMatch]:
    """Return every lexicon phrase found in ``text`` with its span."""
    _build_patterns()
    if not isinstance(text, str) or not text.strip():
        return []
    matches: List[PhraseMatch] = []
    seen: set = set()
    for category, weight, rx in _PATTERNS:
        for m in rx.finditer(text):
            key = (m.start(), m.end(), category)
            if key in seen:
                continue
            seen.add(key)
            matches.append(PhraseMatch(category, m.group(0), weight, m.start(), m.end()))
    for category, weight, rx in _LOOSE:
        for m in rx.finditer(text):
            key = (m.start(), m.end(), category)
            if key in seen:
                continue
            seen.add(key)
            matches.append(PhraseMatch(category, m.group(0), weight, m.start(), m.end()))
    matches.sort(key=lambda p: p.start)
    return matches


def category_scores(matches: List[PhraseMatch]) -> Dict[str, float]:
    """Max weight per category (a category fires once at its strongest)."""
    scores: Dict[str, float] = {}
    for m in matches:
        scores[m.category] = max(scores.get(m.category, 0.0), m.weight)
    return scores


def highlight(text: str, matches: List[PhraseMatch], max_span: int = 4000) -> str:
    """Build a copy of ``text`` with matched phrases wrapped in [[ ]] markers.

    The frontend splits on these markers to colour the exact suspicious words.
    Bounded to ``max_span`` characters so a huge email cannot blow up the DB.
    """
    if not matches:
        return text[:max_span]
    out: List[str] = []
    cursor = 0
    for m in matches:
        if m.start >= max_span:
            break
        out.append(text[cursor:m.start])
        out.append("[[" + text[m.start:min(m.end, max_span)] + "]]")
        cursor = min(m.end, max_span)
    out.append(text[cursor:max_span])
    return "".join(out)
