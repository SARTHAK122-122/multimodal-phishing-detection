"""Regression tests for URL-model explainability (SHAP contributor handling).

Two production bugs are locked down here:

1. Shape handling. On shap 0.46 the RandomForest explainer returns an
   ``(samples, features, classes)`` array. The old code reshaped it into a flat
   2x-length vector, indexed past ``feature_order`` and raised IndexError,
   which was swallowed - so *every* scan silently fell back to impurity
   importances instead of real SHAP values.

2. Fabricated direction. The impurity fallback labelled every feature
   ``direction="risk"`` even though importances are unsigned, producing
   evidence that claimed features "pushed the model toward phishing" when no
   sign information existed at all.
"""
from __future__ import annotations

import numpy as np

from app.models import url_model
from app.models.url_model import _phishing_class_values, _shap_contributors, ENSEMBLE, _load

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"  {'OK ' if condition else 'XX '} {name}" + (f"  [{detail}]" if detail else ""))
    if not condition:
        FAILURES.append(name)


print("### _phishing_class_values shape handling")
a = np.array([[[1.0, 2.0], [3.0, 4.0]]])           # (1, 2 features, 2 classes)
got = _phishing_class_values(a)
check("3D ndarray -> class-1 column", got.tolist() == [2.0, 4.0], str(got.tolist()))

b = np.array([[0.5, -0.5]])                        # (1, 2 features) single class
check("2D ndarray -> row", _phishing_class_values(b).tolist() == [0.5, -0.5])

c = [np.array([[1.0, 2.0]]), np.array([[-1.0, -2.0]])]   # list of per-class arrays
check("list -> class-1 array", _phishing_class_values(c).tolist() == [-1.0, -2.0])

print("\n### _shap_contributors against the real model artifacts")
for name in ENSEMBLE:
    bundle = _load(name)
    if bundle is None:
        print(f"  --  {name} not trained, skipped")
        continue
    model = bundle["model"]
    order = list(bundle.get("features") or [])
    from app.ml.url_features import extract_features
    feats = extract_features("http://paypal-secure-login.verify-account.xyz/login")
    row = np.array([[feats.get(f, 0.0) for f in order]], dtype=float)
    out = _shap_contributors(name, model, row, feats, order)
    check(f"{name}: contributors produced", len(out) > 0)
    signed = [c for c in out if "contribution" in c]
    unsigned = [c for c in out if "importance" in c]
    consistent = all(
        ("direction" in c and
         ((c["contribution"] > 0 and c["direction"] == "risk") or
          (c["contribution"] < 0 and c["direction"] == "safety")))
        for c in signed)
    check(f"{name}: every signed contribution matches its direction", consistent)
    check(f"{name}: fallback items never claim a direction",
          all(c.get("direction") == "neutral" for c in unsigned))
    check(f"{name}: indices within feature order",
          all(c["feature"] in order for c in out))
    print(f"       ({len(signed)} signed SHAP, {len(unsigned)} unsigned fallback)")

print("\n### semantic orientation on known inputs")
phish = url_model.predict("http://paypal-secure-login.verify-account.xyz/login")
if phish.ok and phish.contributors:
    dirs = {c["feature"]: c["direction"] for c in phish.contributors if "contribution" in c}
    check("phishing URL has at least one risk-direction contributor",
          "risk" in dirs.values())
    # Absent HTTPS and many hyphens must read as risk on a bare http phishing host.
    risky = {c["feature"] for c in phish.contributors
             if "contribution" in c and c["direction"] == "risk"}
    check("no-https / hyphens count as risk on the phishing URL",
          {"has_https", "num_hyphens"} & risky != set(), str(risky))

legit = url_model.predict("https://www.paypal.com/signin")
if legit.ok and legit.contributors:
    safety = {c["feature"] for c in legit.contributors
              if "contribution" in c and c["direction"] == "safety"}
    check("real HTTPS contributes toward legitimate", "has_https" in safety, str(safety))

print("\n### pipeline evidence wording follows the direction")
from app.pipelines.website import analyze_website
result = analyze_website("https://www.paypal.com/signin", render=False, fetch=False)
bad = [e for e in result["evidence"]
       if e.get("direction") != "risk"
       and "toward phishing" in e.get("description", "")]
check("no non-risk evidence claims 'toward phishing'", not bad,
      bad[0]["description"] if bad else "")
neutral_claims = [e for e in result["evidence"]
                  if e.get("direction") == "neutral"
                  and e.get("kind") == "INFERENCE"
                  and "influence" not in e.get("description", "").lower()]
check("neutral fallback evidence explains it scores influence only",
      not neutral_claims, neutral_claims[0]["description"] if neutral_claims else "")

print("\n" + ("ALL CHECKS PASSED" if not FAILURES else f"FAILED: {FAILURES}"))
raise SystemExit(1 if FAILURES else 0)
