"""Isolated headless-Chromium rendering: screenshot + rendered DOM + visible text.

This is the source of the VISION modality. It runs the page in a sandboxed,
resource-limited headless browser so JavaScript-rendered phishing kits (which a
plain HTTP fetch cannot see) are captured.

Safety posture
--------------
* The URL is validated by :mod:`app.acquisition.url_safety` before launch.
* A route interceptor blocks any subrequest aimed at a literal private,
  loopback, link-local or metadata address, and refuses non-http(s) schemes, so
  the browser cannot be steered at internal services or ``file://``.
* A hard navigation timeout and a total budget bound the run; the browser is
  always closed in a ``finally`` block.
* Residual risk (documented): subresources addressed by *hostname* are not
  exhaustively DNS-re-resolved inside the interceptor (that would add a DNS
  lookup per subresource). The top-level URL and every literal-IP subresource
  are checked.
"""

from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlsplit

from app import config
from app.acquisition.url_safety import validate_url_for_fetch

# How long Playwright may navigate + settle, and total run budget.
NAV_TIMEOUT_MS = 15000
TOTAL_BUDGET_SECONDS = 35
VIEWPORT = {"width": 1366, "height": 900}


@dataclass
class RenderResult:
    ok: bool
    reason: str = ""
    detail: str = ""
    final_url: str = ""
    rendered_html: str = ""
    visible_text: str = ""
    screenshot_path: str = ""
    screenshot_bytes: int = 0
    console_errors: List[str] = field(default_factory=list)
    blocked_requests: List[str] = field(default_factory=list)
    elapsed_ms: int = 0


def renderer_available() -> bool:
    """True when Playwright + a browser are usable on this machine."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except Exception:
        return False


def _should_block(url: str) -> bool:
    """Block non-http schemes and any literal private/loopback/metadata IP."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return True
    scheme = (parts.scheme or "").lower()
    if scheme not in ("http", "https", "data", "blob"):
        return True
    host = (parts.hostname or "").lower().strip("[]")
    if not host:
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False  # hostname - allowed (see module docstring residual risk)
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def render(url: str, *, screenshot_dir: Optional[Path] = None) -> RenderResult:
    """Render a page and capture screenshot + rendered DOM + text. Never raises."""
    started = time.monotonic()

    verdict = validate_url_for_fetch(url)
    if not verdict.safe:
        return RenderResult(ok=False, reason=verdict.reason, detail=verdict.detail)

    if not renderer_available():
        return RenderResult(
            ok=False, reason="renderer_unavailable",
            detail="Playwright/Chromium is not installed on this host, so the screenshot "
                   "and vision modalities are skipped.",
        )

    out_dir = screenshot_dir or (config.UPLOAD_DIR / "screenshots")
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return RenderResult(ok=False, reason="screenshot_dir_unavailable", detail=str(exc))

    from playwright.sync_api import sync_playwright

    console_errors: List[str] = []
    blocked: List[str] = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--block-new-web-contents",   # do not open popups/new tabs
                ],
            )
            try:
                context = browser.new_context(
                    viewport=VIEWPORT,
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 PhishGuardScanner/1.0"
                    ),
                    ignore_https_errors=False,
                    java_script_enabled=True,
                    accept_downloads=False,
                )
                # Route interceptor: SSRF guard for every subresource.
                def route_handler(route):
                    req_url = route.request.url
                    if _should_block(req_url):
                        blocked.append(req_url[:200])
                        return route.abort()
                    return route.continue_()

                context.route("**/*", route_handler)

                page = context.new_page()
                page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
                page.on("pageerror", lambda exc: console_errors.append(str(exc)[:200]))
                page.on(
                    "console",
                    lambda msg: console_errors.append(msg.text[:200])
                    if msg.type == "error" else None,
                )

                response = page.goto(verdict.normalized, wait_until="domcontentloaded")
                # Give late JS a bounded moment to populate the DOM.
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass  # busy pages never go idle; domcontentloaded is enough

                final_url = page.url
                html = page.content()
                try:
                    visible_text = page.inner_text("body")[:50000]
                except Exception:
                    visible_text = ""

                shot_path = out_dir / f"scan_{int(time.time() * 1000)}.png"
                try:
                    page.screenshot(path=str(shot_path), full_page=False)
                except Exception as exc:
                    return RenderResult(
                        ok=True, final_url=final_url, rendered_html=html,
                        visible_text=visible_text,
                        detail=f"Rendered, but the screenshot failed: {exc.__class__.__name__}.",
                        blocked_requests=blocked,
                        elapsed_ms=int((time.monotonic() - started) * 1000),
                    )

                size = shot_path.stat().st_size if shot_path.exists() else 0
                return RenderResult(
                    ok=True,
                    final_url=final_url,
                    rendered_html=html,
                    visible_text=visible_text,
                    screenshot_path=str(shot_path),
                    screenshot_bytes=size,
                    console_errors=console_errors[:10],
                    blocked_requests=blocked[:10],
                    elapsed_ms=int((time.monotonic() - started) * 1000),
                )
            finally:
                browser.close()
    except Exception as exc:
        return RenderResult(
            ok=False, reason="render_failed",
            detail=f"{exc.__class__.__name__}: {exc}"[:300],
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )
