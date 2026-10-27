"""Regression tests for URL-fetch safety and the fetcher's deny paths.

Covers the bug where ``_deny()`` crashed with "got multiple values for keyword
argument 'final_url'" whenever a caller (e.g. the HTTP-status deny at >=400 or
an unsafe redirect) passed the last safe hop through ``**kw``. That crash
turned a handled denial into an unhandled 500 - exactly the kind of failure
that must degrade into an honest "fetch failed" modality, never into silence.
"""
from __future__ import annotations

from app.acquisition.fetcher import FetchResult, _deny, fetch_html
from app.acquisition.url_safety import validate_url_for_fetch

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"  {'OK ' if condition else 'XX '} {name}" + (f"  [{detail}]" if detail else ""))
    if not condition:
        FAILURES.append(name)


print("### _deny() keyword handling")
r = _deny("http_status_403", "The server answered with HTTP 403.",
          url="https://x.example", final_url="https://x.example/login",
          status_code=403)
check("caller-provided final_url wins", isinstance(r, FetchResult) and r.final_url == "https://x.example/login")
check("caller-provided extra field kept", getattr(r, "status_code", None) == 403)
check("deny is never ok", r.ok is False)

r2 = _deny("timeout", "budget exceeded", url="https://y.example")
check("default final_url falls back to url", r2.final_url == "https://y.example")
check("reason and detail preserved", r2.reason == "timeout" and r2.detail == "budget exceeded")

print("\n### fetch_html refuses unsafe targets without touching the network")
for url, expected in [
    ("javascript:alert(1)", "scheme"),
    ("file:///etc/passwd", "scheme"),
    ("ftp://evil.example/x", "scheme"),
    ("http://127.0.0.1:6379/", "private"),
    ("http://169.254.169.254/latest/meta-data/", "metadata"),
    ("http://192.168.1.1/admin", "private"),
]:
    result = fetch_html(url)
    reason = (result.reason or "").lower()
    check(f"denied: {url}", result.ok is False and bool(result.reason), result.reason)

print("\n### validate_url_for_fetch verdicts")
safe = validate_url_for_fetch("https://example.com/path")
check("example.com is fetchable", safe.safe is True, safe.normalized or "")
unsafe = validate_url_for_fetch("http://[::1]/")
check("loopback IPv6 refused", unsafe.safe is False, unsafe.reason)

print("\n" + ("ALL CHECKS PASSED" if not FAILURES else f"FAILED: {FAILURES}"))
raise SystemExit(1 if FAILURES else 0)
