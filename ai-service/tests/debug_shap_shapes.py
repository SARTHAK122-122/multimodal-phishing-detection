"""Print exact shap_values shapes/expected_value for both URL models."""
from __future__ import annotations

import numpy as np
import shap

from app.ml.url_features import extract_features
from app.models.url_model import ENSEMBLE, _bundle_feature_order, _load

for name in ENSEMBLE:
    bundle = _load(name)
    if bundle is None:
        print(f"{name}: not available")
        continue
    model = bundle["model"]
    order = _bundle_feature_order(bundle)
    print(f"\n=== {name}  n_features_in_={getattr(model, 'n_features_in_', '?')} "
          f"bundle_features={len(order)}")
    feats = extract_features("https://www.paypal.com/signin")
    row = np.array([[feats.get(f, 0.0) for f in order]], dtype=float)
    explainer = shap.TreeExplainer(model)
    sv = explainer.shap_values(row)
    print(f"  type(sv)={type(sv).__name__}")
    if isinstance(sv, list):
        print(f"  list len={len(sv)}  shapes={[np.asarray(s).shape for s in sv]}")
    else:
        print(f"  ndarray shape={np.asarray(sv).shape}")
    ev = explainer.expected_value
    print(f"  expected_value={ev}")
