"""URL feature extraction - the single source of truth for the URL modality.

Every function here works on the **raw URL string only** (no page fetch, no
network). Training (``training/train_url_models.py``) and inference (the scan
pipeline) MUST both call :func:`extract_features` so the feature vector seen
by a model at prediction time is identical to the one it was trained on.

FEATURE_NAMES is the column order used to build matrices; it is frozen per
version and stored inside the saved model bundle. Inference reads the order
from the bundle (see ``models/url_model.py``), so a bundle trained on an older
schema keeps working even after new features are appended here.

Version 2 (expanded schema)
---------------------------
The original 16 features over-fit the PhiUSIIL URL style (long, letter-heavy,
query-rich) and produced false positives on short, real, legitimate URLs such
as ``https://github.com/``. Version 2 appends features that are invariant to
dataset style and reflect how phishing URLs are actually built in the wild:
rare TLDs, punycode/homoglyph hosts, high-entropy random strings, deep paths,
URL shorteners, and brand-name typosquatting in subdomains of unrelated domains.
"""

from __future__ import annotations

import ipaddress
import math
from collections import Counter
from typing import Dict, List, Tuple
from urllib.parse import urlsplit

# Order matters: this is the exact column order passed to the estimators.
FEATURE_NAMES: List[str] = [
    # Frozen URL-modality training schema (v3, host-structure only).
    # See EXTRACTED_FEATURE_NAMES below for everything the extractor computes.
    "hostname_length",
    "num_dots",
    "num_hyphens",
    "num_subdomains",
    "has_ip_host",
    "has_https",
    "num_at_symbols",
    "tld_length",
    "is_suspicious_tld",
    "is_common_tld",
    "has_punycode",
    "host_digit_count",
    "host_entropy",
    "brand_in_unrelated_domain",
    "is_shortener",
    "num_labels",
]

# Everything the extractor computes (superset). Path/query/digit features are
# retained for research/ablation and future use but are NOT part of the frozen
# training schema - see the artifact note in the module docstring.
EXTRACTED_FEATURE_NAMES: List[str] = FEATURE_NAMES + [
    "url_length",
    "path_length",
    "num_question_marks",
    "num_equals",
    "num_percent_signs",
    "digit_ratio",
    "letter_ratio",
    "suspicious_keyword_count",
    "max_digit_run",
    "path_depth",
    "num_query_params",
    "path_entropy",
    "has_port_specified",
    "has_double_slash_in_path",
]

# Keywords checked case-insensitively against the whole URL. The list is
# deliberately explicit - keywords are never inferred or learned here.
SUSPICIOUS_KEYWORDS: List[str] = [
    "login", "signin", "sign-in", "verify", "verification", "secure", "security",
    "account", "update", "confirm", "password", "banking", "paypal", "ebay",
    "apple", "microsoft", "google", "amazon", "netflix", "urgent", "suspend",
    "suspended", "invoice", "billing", "wallet", "authenticate", "authorization",
    "session", "unlock", "recover", "reactivate", "statement", "webscr",
]

# TLDs disproportionately represented in phishing corpora (not a blocklist -
# a numeric risk feature the model weighs with everything else).
SUSPICIOUS_TLDS = {
    "xyz", "top", "tk", "ml", "ga", "cf", "gq", "ru", "cn", "info", "biz",
    "club", "online", "site", "store", "icu", "live", "work", "click", "link",
    "rest", "wang", "buzz", "monster", "quest", "cfd", "sbs", "bond",
}

# Broadly trusted, well-regulated TLDs.
COMMON_TLDS = {
    "com", "org", "net", "edu", "gov", "mil", "int", "io", "co", "me", "app",
    "dev", "ai", "sh", "uk", "us", "ca", "de", "fr", "jp", "au", "in", "ch",
    "nl", "se", "no", "es", "it", "br", "za", "kr", "sg", "hk", "nz", "ie",
}

# Well-known URL shorteners - a redirect wrapper, not proof of malice.
SHORTENERS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly",
    "adf.ly", "shorte.st", "lnkd.in", "youtu.be", "rb.gy", "cutt.ly", "bl.ink",
    "s.id", "v.gd", "tiny.cc", "soo.gd", "urlzs.com",
}

# Brands commonly impersonated, with their real registrable domain. A brand
# token that appears in a hostname NOT ending in its real domain = typosquat.
BRAND_DOMAINS: Dict[str, str] = {
    "paypal": "paypal.com",
    "google": "google.com",
    "apple": "apple.com",
    "microsoft": "microsoft.com",
    "amazon": "amazon.com",
    "netflix": "netflix.com",
    "instagram": "instagram.com",
    "facebook": "facebook.com",
    "whatsapp": "whatsapp.com",
    "bankofamerica": "bankofamerica.com",
    "hdfcbank": "hdfcbank.com",
    "citibank": "citibank.com",
    "chase": "chase.com",
    "allegro": "allegro.pl",
    "github": "github.com",
}


def _zero() -> Dict[str, float]:
    return {name: 0.0 for name in EXTRACTED_FEATURE_NAMES}


def _entropy(text: str) -> float:
    """Shannon entropy (bits/char) - high for random phishing tokens."""
    if not text:
        return 0.0
    counts = Counter(text)
    length = len(text)
    return -sum((c / length) * math.log2(c / length) for c in counts.values())


def _max_digit_run(text: str) -> int:
    best = cur = 0
    for ch in text:
        cur = cur + 1 if ch.isdigit() else 0
        best = max(best, cur)
    return best


def _brand_typosquat(host: str) -> Tuple[int, str]:
    """Return (flag, evidence) when a brand name sits in a host whose real
    domain is NOT that brand - the classic 'paypal.com.secure-login.xyz'."""
    if not host:
        return 0, ""
    labels = [l for l in host.split(".") if l]
    # Registrable domain ~ last two labels (co.uk style handled loosely).
    registrable = ".".join(labels[-2:]) if len(labels) >= 2 else host
    for brand, real_domain in BRAND_DOMAINS.items():
        if brand in host and not (host == real_domain or host.endswith("." + real_domain)):
            # Brand appears but host is not the real domain -> suspicious.
            return 1, f"{brand} in {host} (real is {real_domain})"
    return 0, ""


def extract_features(url: str) -> Dict[str, float]:
    """Extract the URL features from one raw URL string.

    Never raises: an empty/invalid URL yields all-zero features so a single
    bad row cannot crash a batch job. The caller can count empties separately.
    """
    if not isinstance(url, str) or not url.strip():
        return _zero()

    raw = url.strip()
    # urlsplit needs a scheme to fill netloc; default to http for scheme-less
    # input ("example.com/x") - has_https still reflects the ORIGINAL string.
    parsable = raw if "://" in raw else "http://" + raw.lstrip("/")

    try:
        parts = urlsplit(parsable)
        host = (parts.hostname or "").lower()
        path = parts.path or ""
        port_explicit = parts.port is not None
    except ValueError:
        host, path, port_explicit = "", "", False

    length = len(raw)
    digits = sum(ch.isdigit() for ch in raw)
    letters = sum(ch.isalpha() for ch in raw)

    # --- hostname ---
    host_labels = [lbl for lbl in host.split(".") if lbl]
    num_dots = host.count(".")
    num_subdomains = max(len(host_labels) - 2, 0)
    num_labels = len(host_labels)
    is_ip = False
    if host:
        try:
            ipaddress.ip_address(host.strip("[]"))
            is_ip = True
        except ValueError:
            is_ip = False
    tld = host_labels[-1] if host_labels and not is_ip else ""
    tld_length = len(tld)

    lowered = raw.lower()
    keyword_count = sum(1 for kw in SUSPICIOUS_KEYWORDS if kw in lowered)
    typosquat, _ = _brand_typosquat(host)

    # Path depth & query params.
    path_segments = [s for s in path.split("/") if s]
    path_depth = len(path_segments)
    try:
        num_params = len([p for p in (parts.query or "").split("&") if p]) if parts.query else 0
    except ValueError:
        num_params = 0

    # Double slash in path (protocol-relative or path traversal trick).
    dbl_in_path = 1 if path.startswith("//") or "//" in path.lstrip("/") else 0

    return {
        # --- v1 ---
        "url_length": float(length),
        "hostname_length": float(len(host)),
        "path_length": float(len(path)),
        "num_dots": float(num_dots),
        "num_hyphens": float(raw.count("-")),
        "num_subdomains": float(num_subdomains),
        "has_ip_host": 1.0 if is_ip else 0.0,
        "has_https": 1.0 if lowered.startswith("https://") else 0.0,
        "num_at_symbols": float(raw.count("@")),
        "num_question_marks": float(raw.count("?")),
        "num_equals": float(raw.count("=")),
        "num_percent_signs": float(raw.count("%")),
        "digit_ratio": digits / length if length else 0.0,
        "letter_ratio": letters / length if length else 0.0,
        "suspicious_keyword_count": float(keyword_count),
        "tld_length": float(tld_length),
        # --- v2 ---
        "is_suspicious_tld": 1.0 if tld in SUSPICIOUS_TLDS else 0.0,
        "is_common_tld": 1.0 if tld in COMMON_TLDS else 0.0,
        "has_punycode": 1.0 if "xn--" in host else 0.0,
        "host_digit_count": float(sum(c.isdigit() for c in host)),
        "max_digit_run": float(_max_digit_run(raw)),
        "path_depth": float(path_depth),
        "num_query_params": float(num_params),
        "host_entropy": round(_entropy(host), 4),
        "path_entropy": round(_entropy(path), 4),
        "brand_in_unrelated_domain": float(typosquat),
        "is_shortener": 1.0 if host in SHORTENERS else 0.0,
        "has_port_specified": 1.0 if port_explicit else 0.0,
        "has_double_slash_in_path": float(dbl_in_path),
        "num_labels": float(num_labels),
    }


def extract_rows(urls: List[str]) -> List[Dict[str, float]]:
    """Extract features for a batch of URLs, preserving order."""
    return [extract_features(u) for u in urls]
