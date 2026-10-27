"""Verify contributor orientation after the shape fix."""
from __future__ import annotations

from app.models import url_model

for url, tag in [("https://www.paypal.com/signin", "LEGIT"),
                 ("https://example.com", "LEGIT"),
                 ("http://paypal-secure-login.verify-account.xyz/login", "PHISH")]:
    pred = url_model.predict(url)
    print(f"\n{tag} P={pred.probability:.4f} models={pred.models_used}  {url}")
    for c in pred.contributors[:6]:
        if "contribution" in c:
            print(f"   {c['feature']:22} value={c['value']:6} shap={c['contribution']:+.4f} {c['direction']}")
        else:
            print(f"   {c['feature']:22} value={c['value']:6} importance={c.get('importance')} {c['direction']}")
