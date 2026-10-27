"""Diagnose why a benign URL scores as phishing. Dumps features + SHAP + the
model's view, and checks a few clearly-benign and clearly-phishing URLs."""
from __future__ import annotations
from app.models import url_model
from app.ml.url_features import extract_features, FEATURE_NAMES

urls = [
    "https://www.wikipedia.org/wiki/Phishing",
    "https://www.google.com/",
    "https://github.com/",
    "https://example.com/",
    "http://paypal-secure-login.verify-account.xyz/index.html?user=1",
    "http://193.0.12.44/paypal/update/session/verify.php",
]
for u in urls:
    p = url_model.predict(u)
    print(f"\n=== {u}")
    print(f"  P(phishing) = {p.probability}")
    f = extract_features(u)
    nz = {k: round(v, 3) for k, v in f.items() if v}
    print(f"  features(non-zero): {nz}")
    print(f"  top SHAP: {[(c['feature'], c.get('contribution', c.get('importance'))) for c in p.contributors[:5]]}")
