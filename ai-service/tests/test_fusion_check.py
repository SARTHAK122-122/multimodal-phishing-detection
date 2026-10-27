"""Empirical fusion check: run the full pipeline on real benign sites (full
fetch+render) and phishing-pattern URLs, print verdicts. This is the demo
correctness gate: benign -> LEGITIMATE, phishing -> PHISHING/SUSPICIOUS."""
from __future__ import annotations
from app.pipelines.website import analyze_website

benign = [
    "https://example.com",
    "https://github.com",
    "https://www.python.org",
    "https://www.wikipedia.org",
]
phish = [
    "http://paypal-secure-login.verify-account.xyz/login",
    "http://193.0.12.44/paypal/update/session/verify.php",
    "https://appleid-verify.confirm-account.tk/login",
]

print("### BENIGN (expect LEGITIMATE)")
for u in benign:
    r = analyze_website(u)
    mods = {m['modality']: (m['status'], m['riskScore']) for m in r['modalities']}
    print(f"  {r['classification']:10} {r['riskLevel']:8} score={r['riskScore']:.3f}  {u}")
    print(f"      {mods}")

print("\n### PHISHING-PATTERN (expect PHISHING/SUSPICIOUS)")
for u in phish:
    r = analyze_website(u)
    print(f"  {r['classification']:10} {r['riskLevel']:8} score={r['riskScore']:.3f}  {u}")
