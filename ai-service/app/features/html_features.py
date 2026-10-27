"""HTML / DOM feature extraction and rule-based findings.

Given the raw HTML of a page this module produces two things:

1. ``features`` - a fixed-order numeric vector, designed so a Random Forest can
   later be trained on it (schema is frozen in ``FEATURE_NAMES``).
2. ``findings`` - direct, verifiable observations (an actual password field, an
   actual form that posts to another domain) surfaced as evidence.

Everything here is a **measurement**, never a verdict. A password field alone
does not make a page phishing - the risk engine weighs it together with the URL,
text and vision modalities.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from app.findings import Finding

# Frozen schema. A trained html_* model stores this order inside its bundle.
FEATURE_NAMES: List[str] = [
    "num_forms",
    "num_password_fields",
    "num_hidden_fields",
    "num_text_inputs",
    "num_password_forms",
    "form_action_external",
    "form_action_http_on_https",
    "num_iframes",
    "iframe_src_external",
    "num_external_scripts",
    "num_links",
    "num_external_links",
    "link_text_ratio_external",
    "num_images",
    "has_title",
    "title_length",
    "has_meta_viewport",
    "num_meta_refresh",
    "has_favicon",
    "has_password_autocomplete",
    "html_length",
    "num_input_elements",
    "external_resource_ratio",
]


@dataclass
class HtmlAnalysis:
    features: Dict[str, float] = field(default_factory=dict)
    findings: List[Finding] = field(default_factory=list)
    forms: List[dict] = field(default_factory=list)
    links_sample: List[str] = field(default_factory=list)
    title: str = ""
    ok: bool = True
    detail: str = ""

    def as_evidence(self) -> dict:
        return {
            "ok": self.ok,
            "title": self.title,
            "forms": self.forms[:20],
            "featureSummary": {k: self.features.get(k, 0.0) for k in FEATURE_NAMES},
        }


def _zero() -> Dict[str, float]:
    return {name: 0.0 for name in FEATURE_NAMES}


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _is_external(target: str, base_host: str, page_host: str) -> bool:
    """True when ``target`` points at a different registrable host than the page."""
    if not target:
        return False
    absolute = urljoin(f"https://{page_host}/" if page_host else "/", target)
    host = _host(absolute)
    if not host:
        return False
    if page_host:
        return host != page_host
    return host != base_host


def analyze_html(html: str, page_url: str) -> HtmlAnalysis:
    """Parse HTML and extract DOM features + findings. Never raises."""
    result = HtmlAnalysis(features=_zero())
    if not isinstance(html, str) or not html.strip():
        result.ok = False
        result.detail = "No HTML was available for DOM analysis."
        return result

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception as exc:  # pragma: no cover - lxml is very tolerant
        result.ok = False
        result.detail = f"HTML could not be parsed: {exc.__class__.__name__}."
        return result

    page_host = _host(page_url)
    feats = result.features
    feats["html_length"] = float(len(html))

    # --- title ---
    title_tag = soup.find("title")
    title = (title_tag.get_text(strip=True) if title_tag else "") or ""
    result.title = title[:300]
    feats["has_title"] = 1.0 if title else 0.0
    feats["title_length"] = float(len(title))
    if not title:
        result.findings.append(Finding(
            modality="HTML", evidence_type="missing_title",
            description="The page has no <title>, which is unusual for a legitimate site.",
            severity="LOW", supporting_value="", direction="risk",
        ))

    # --- forms ---
    forms = soup.find_all("form")
    feats["num_forms"] = float(len(forms))
    password_fields_total = 0
    external_form_actions = 0
    http_on_https = 0
    form_records: List[dict] = []

    for form in forms:
        action = (form.get("action") or "").strip()
        method = (form.get("method") or "get").lower()
        absolute_action = urljoin(page_url, action) if action else page_url
        inputs = form.find_all("input")
        pw_inputs = [i for i in inputs if (i.get("type") or "").lower() == "password"]
        hidden_inputs = [i for i in inputs if (i.get("type") or "").lower() == "hidden"]
        text_inputs = [
            i for i in inputs
            if (i.get("type") or "text").lower() in ("text", "email", "tel")
        ]
        password_fields_total += len(pw_inputs)
        external = _is_external(absolute_action, page_host, page_host)

        record = {
            "action": absolute_action[:500],
            "method": method,
            "passwordFields": len(pw_inputs),
            "hiddenFields": len(hidden_inputs),
            "textInputs": len(text_inputs),
            "externalAction": external,
        }
        form_records.append(record)

        if pw_inputs:
            feats["num_password_forms"] += 1.0
            if external:
                external_form_actions += 1
                result.findings.append(Finding(
                    modality="HTML", evidence_type="password_form_external_action",
                    description=(
                        "A login form (password field) submits to a different domain than "
                        "the page itself. Legitimate sign-in pages post to their own domain."
                    ),
                    severity="HIGH", supporting_value=absolute_action[:300], direction="risk",
                ))
            elif method == "get":
                result.findings.append(Finding(
                    modality="HTML", evidence_type="password_form_get_method",
                    description="A login form submits with method=GET, which would expose the "
                                "password in the URL and browser history.",
                    severity="MEDIUM", supporting_value=absolute_action[:300], direction="risk",
                ))
            else:
                result.findings.append(Finding(
                    modality="HTML", evidence_type="password_form_detected",
                    description="The page contains a password field. This is expected on real "
                                "login pages - considered together with the URL and brand.",
                    severity="LOW", supporting_value=absolute_action[:300], direction="neutral",
                ))

        if external and not pw_inputs:
            external_form_actions += 1
            result.findings.append(Finding(
                modality="HTML", evidence_type="external_form_action",
                description="A form on this page submits data to an external domain.",
                severity="MEDIUM", supporting_value=absolute_action[:300], direction="risk",
            ))

        if page_url.startswith("https://") and absolute_action.startswith("http://"):
            http_on_https += 1
            result.findings.append(Finding(
                modality="HTML", evidence_type="insecure_form_submission",
                description="A form on an HTTPS page submits over plain HTTP, so the data "
                            "could be intercepted.",
                severity="MEDIUM", supporting_value=absolute_action[:300], direction="risk",
            ))

    feats["num_password_fields"] = float(password_fields_total)
    feats["form_action_external"] = float(external_form_actions)
    feats["form_action_http_on_https"] = float(http_on_https)
    result.forms = form_records

    feats["num_hidden_fields"] = float(len(soup.find_all("input", attrs={"type": "hidden"})))
    all_inputs = soup.find_all("input")
    feats["num_input_elements"] = float(len(all_inputs))
    feats["num_text_inputs"] = float(sum(
        1 for i in all_inputs if (i.get("type") or "text").lower() in ("text", "email", "tel")
    ))

    # autocomplete="on" for password fields weakens credential safety posture.
    autocompleted = soup.find_all("input", attrs={"autocomplete": lambda v: v and "on" in v.lower()})
    has_pw_autocomplete = any(
        (i.get("type") or "").lower() == "password" for i in autocompleted
    )
    feats["has_password_autocomplete"] = 1.0 if has_pw_autocomplete else 0.0
    if has_pw_autocomplete:
        result.findings.append(Finding(
            modality="HTML", evidence_type="password_autocomplete_enabled",
            description="Password fields allow browser autocomplete, a weak security posture "
                        "often seen on quickly-built phishing pages.",
            severity="LOW", direction="risk",
        ))

    # --- iframes ---
    iframes = soup.find_all("iframe")
    feats["num_iframes"] = float(len(iframes))
    iframe_external = 0
    for iframe in iframes:
        src = (iframe.get("src") or "").strip()
        if src and _is_external(src, page_host, page_host):
            iframe_external += 1
    feats["iframe_src_external"] = float(iframe_external)
    if iframe_external:
        result.findings.append(Finding(
            modality="HTML", evidence_type="external_iframe",
            description=f"{iframe_external} iframe(s) load content from another domain, which "
                        "can overlay a fake login UI on an unrelated page.",
            severity="MEDIUM", supporting_value=str(iframe_external), direction="risk",
        ))

    # --- scripts & resources ---
    scripts = soup.find_all("script", src=True)
    external_scripts = [s for s in scripts if _is_external(s.get("src", ""), page_host, page_host)]
    feats["num_external_scripts"] = float(len(external_scripts))
    feats["external_resource_ratio"] = (
        len(external_scripts) / len(scripts) if scripts else 0.0
    )
    if len(external_scripts) >= 5:
        result.findings.append(Finding(
            modality="HTML", evidence_type="many_external_scripts",
            description=f"The page loads {len(external_scripts)} external scripts, increasing "
                        "the attack surface and the chance of injected content.",
            severity="LOW", supporting_value=str(len(external_scripts)), direction="neutral",
        ))

    # --- meta ---
    feats["has_meta_viewport"] = 1.0 if soup.find("meta", attrs={"name": "viewport"}) else 0.0
    meta_refresh = soup.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "refresh"})
    feats["num_meta_refresh"] = 1.0 if meta_refresh else 0.0
    if meta_refresh:
        content = (meta_refresh.get("content") or "")[:200]
        result.findings.append(Finding(
            modality="HTML", evidence_type="meta_refresh_redirect",
            description="The page uses a meta-refresh redirect, a common way to bounce users "
                        "through an intermediate domain.",
            severity="LOW", supporting_value=content, direction="risk",
        ))

    # --- favicon (brand presence) ---
    favicon_href = ""
    for link in soup.find_all("link"):
        rel = " ".join(link.get("rel") or []).lower()
        if "icon" in rel:
            favicon_href = (link.get("href") or "")[:200]
            break
    feats["has_favicon"] = 1.0 if favicon_href else 0.0
    if not favicon_href:
        result.findings.append(Finding(
            modality="HTML", evidence_type="no_favicon",
            description="The page declares no favicon; most established sites ship one.",
            severity="INFO", direction="neutral",
        ))

    # --- links ---
    anchors = soup.find_all("a", href=True)
    feats["num_links"] = float(len(anchors))
    external_links: List[str] = []
    for a in anchors:
        href = (a.get("href") or "").strip()
        if href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue
        absolute = urljoin(page_url, href)
        if _is_external(absolute, page_host, page_host):
            external_links.append(absolute)
    feats["num_external_links"] = float(len(external_links))
    feats["link_text_ratio_external"] = (len(external_links) / len(anchors)) if anchors else 0.0
    result.links_sample = external_links[:25]

    # Flag only when a page with a real link structure sends everything
    # off-site; a sparse page with one external reference (e.g. example.com's
    # lone iana.org link) is not suspicious on its own.
    if external_links and len(anchors) >= 4 and len(external_links) == len([
        a for a in anchors if (a.get("href") or "").strip()
        and not (a.get("href") or "").startswith(("#", "javascript:", "mailto:", "tel:"))
    ]):
        result.findings.append(Finding(
            modality="HTML", evidence_type="all_links_external",
            description="Every link on the page points to a different domain, which is "
                        "characteristic of a landing/staging page rather than a real site.",
            severity="MEDIUM", supporting_value=external_links[0][:200], direction="risk",
        ))

    # --- images ---
    feats["num_images"] = float(len(soup.find_all("img")))

    # --- copyright footer (mild legitimacy signal) ---
    text = soup.get_text(" ", strip=True).lower()
    if "copyright" in text or "\u00a9" in soup.get_text():
        result.findings.append(Finding(
            modality="HTML", evidence_type="copyright_notice",
            description="The page carries a copyright notice, a mild legitimacy signal.",
            severity="INFO", direction="safety",
        ))

    # --- brand impersonation heuristic: password form + claimed brand in title ---
    if password_fields_total and title:
        brand_tokens = ("paypal", "google", "apple", "microsoft", "amazon", "netflix",
                        "instagram", "facebook", "whatsapp", "bank", "hdfc", "sbi", "icici")
        title_lower = title.lower()
        matched = [b for b in brand_tokens if b in title_lower]
        if matched and external_form_actions:
            result.findings.append(Finding(
                modality="HTML", evidence_type="brand_claim_with_external_form",
                description=(
                    f"The page title claims the brand '{matched[0]}' while its login form "
                    "submits to a different domain - a strong brand-impersonation signal."
                ),
                severity="CRITICAL", supporting_value=title[:200], direction="risk",
            ))

    return result
