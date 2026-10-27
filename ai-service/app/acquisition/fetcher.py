"""Bounded, SSRF-safe HTTP fetching for the website modality.

Design rules enforced here:
* every hop (initial + each redirect) goes through :func:`url_safety.validate_url_for_fetch`
* the response body is streamed and truncated at ``MAX_FETCH_BYTES``
* a total wall-clock budget bounds the whole operation, not just one read
* only ``text/html``-ish content is kept; anything else is refused with a
  typed reason so the caller can report the modality honestly
* no cookies, no credential prompts, no automatic auth - this is a scanner,
  not a browser session
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

from app import config
from app.acquisition.url_safety import UrlVerdict, validate_url_for_fetch

# A browser-like Accept header reduces "please enable JS" interstitials, but we
# deliberately do NOT send a cookie jar or follow cross-origin credential hops.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 PhishGuardScanner/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Content types we will parse as a webpage.
_HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain")


@dataclass
class FetchResult:
    """Outcome of fetching one URL. ``ok`` is False for any refusal/failure."""

    ok: bool
    url: str = ""
    final_url: str = ""
    status_code: Optional[int] = None
    content_type: str = ""
    html: str = ""
    bytes_read: int = 0
    truncated: bool = False
    elapsed_ms: int = 0
    redirect_chain: List[str] = field(default_factory=list)
    reason: str = ""
    detail: str = ""
    verdict: Optional[UrlVerdict] = None

    def as_evidence(self) -> dict:
        return {
            "ok": self.ok,
            "status": self.status_code,
            "contentType": self.content_type,
            "bytesRead": self.bytes_read,
            "truncated": self.truncated,
            "elapsedMs": self.elapsed_ms,
            "redirectChain": self.redirect_chain,
            "reason": self.reason,
            "detail": self.detail,
        }


def _deny(reason: str, detail: str, url: str = "", **kw) -> FetchResult:
    """Builds a failed FetchResult. Callers may override ``final_url`` (e.g. the
    last safe hop before a blocked redirect) through ``**kw``."""
    kw.setdefault("final_url", url)
    return FetchResult(ok=False, url=url, reason=reason, detail=detail, **kw)


def fetch_html(url: str, *, max_bytes: Optional[int] = None,
               max_redirects: Optional[int] = None,
               timeout: Optional[int] = None) -> FetchResult:
    """Fetch a webpage's HTML safely. Never raises.

    Returns a :class:`FetchResult`; when ``ok`` is True, ``html`` holds up to
    ``max_bytes`` of the response body and ``final_url`` is the last hop.
    """
    started = time.monotonic()
    limit = max_bytes or config.MAX_FETCH_BYTES
    redirects = max_redirects if max_redirects is not None else config.MAX_REDIRECTS
    overall = timeout or config.FETCH_TIMEOUT_SECONDS

    verdict = validate_url_for_fetch(url)
    if not verdict.safe:
        return _deny(verdict.reason, verdict.detail, url=url, verdict=verdict)

    current = verdict.normalized
    chain: List[str] = []
    session = requests.Session()
    session.cookies.clear()

    try:
        for hop in range(redirects + 1):
            remaining = overall - (time.monotonic() - started)
            if remaining <= 0:
                return _deny("timeout", "The fetch exceeded its total time budget.",
                             url=url, redirect_chain=chain, verdict=verdict)

            resp = session.get(
                current,
                headers=_HEADERS,
                timeout=(min(remaining, 8), remaining),
                allow_redirects=False,
                stream=True,
            )

            # Redirect hop -> re-validate destination before following.
            if resp.is_redirect or resp.is_permanent_redirect:
                location = resp.headers.get("Location", "")
                resp.close()
                if not location:
                    return _deny("redirect_without_location", "A redirect carried no Location header.",
                                 url=url, final_url=current, redirect_chain=chain, verdict=verdict)
                target = requests.compat.urljoin(current, location)
                hop_verdict = validate_url_for_fetch(target)
                if not hop_verdict.safe:
                    return _deny(
                        "unsafe_redirect",
                        f"Redirect to '{target}' was blocked: {hop_verdict.detail}",
                        url=url, final_url=current, redirect_chain=chain, verdict=verdict,
                    )
                chain.append(target)
                current = hop_verdict.normalized
                continue

            # Non-redirect terminal response.
            status = resp.status_code
            ctype = (resp.headers.get("Content-Type", "") or "").split(";")[0].strip().lower()

            if status >= 400:
                resp.close()
                return _deny(
                    f"http_status_{status}",
                    f"The server answered with HTTP {status}.",
                    url=url, final_url=current, status_code=status, redirect_chain=chain,
                    verdict=verdict,
                )

            if ctype and not any(ctype.startswith(t) for t in _HTML_CONTENT_TYPES):
                resp.close()
                return _deny(
                    "unsupported_content_type",
                    f"The response is '{ctype}', not a webpage; the website modality only "
                    "analyses HTML pages.",
                    url=url, final_url=current, status_code=status, content_type=ctype,
                    redirect_chain=chain, verdict=verdict,
                )

            # Stream with a hard byte cap.
            chunks: List[bytes] = []
            read = 0
            truncated = False
            try:
                for chunk in resp.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    read += len(chunk)
                    if read > limit:
                        chunks.append(chunk[: max(0, limit - (read - len(chunk)))])
                        truncated = True
                        break
                    chunks.append(chunk)
                    if time.monotonic() - started > overall:
                        truncated = True
                        break
            finally:
                resp.close()

            raw_body = b"".join(chunks)
            charset = resp.encoding or "utf-8"
            try:
                html = raw_body.decode(charset, errors="replace")
            except LookupError:
                html = raw_body.decode("utf-8", errors="replace")

            return FetchResult(
                ok=True,
                url=url,
                final_url=current,
                status_code=status,
                content_type=ctype,
                html=html,
                bytes_read=len(raw_body),
                truncated=truncated,
                elapsed_ms=int((time.monotonic() - started) * 1000),
                redirect_chain=chain,
                verdict=verdict,
            )

        return _deny("too_many_redirects", f"Exceeded the {redirects}-redirect limit.",
                     url=url, redirect_chain=chain, verdict=verdict)

    except requests.exceptions.Timeout:
        return _deny("timeout", "The request timed out.", url=url, redirect_chain=chain, verdict=verdict)
    except requests.exceptions.SSLError as exc:
        return _deny("ssl_error", f"TLS handshake failed: {exc}", url=url, redirect_chain=chain, verdict=verdict)
    except requests.exceptions.ConnectionError as exc:
        return _deny("connection_error", f"Could not connect: {exc.__class__.__name__}.",
                     url=url, redirect_chain=chain, verdict=verdict)
    except requests.exceptions.RequestException as exc:
        return _deny("request_failed", f"{exc.__class__.__name__}: {exc}",
                     url=url, redirect_chain=chain, verdict=verdict)
    finally:
        session.close()
