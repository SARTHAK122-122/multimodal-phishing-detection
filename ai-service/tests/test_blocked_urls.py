"""Blocked/unsafe URLs must never classify as clean (LEGITIMATE)."""
from __future__ import annotations
from app.pipelines.website import analyze_website

CASES = [
    "javascript:alert(1)",
    "file:///etc/passwd",
    "ftp://evil.com/x",
    "http://169.254.169.254/latest/meta-data/",
    "http://user:pass@evil.com/",
    "http://127.0.0.1:6379/",
]

fail = 0
for u in CASES:
    r = analyze_website(u, render=False, fetch=False)
    ok = r["classification"] != "LEGITIMATE"
    if not ok:
        fail += 1
    print(f"{'OK' if ok else 'XX'} {r['classification']:11} {r['riskLevel']:9} "
          f"score={r['riskScore']}  {u}")

print(f"\n{len(CASES) - fail}/{len(CASES)} blocked URLs refused a clean verdict")
