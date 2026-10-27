"""Where do real benign URLs fall relative to the dataset's legitimate
distribution? Prints percentile of each real URL's key features inside the
legit (label=1) training distribution, plus the SHAP breakdown with base value."""
from __future__ import annotations
import pandas as pd, numpy as np
from app import config
from app.ml.url_features import extract_rows, FEATURE_NAMES, extract_features
from app.models import url_model
import shap

csv = config.PROJECT_ROOT / "datasets" / "sources" / "PhiUSIIL_Phishing_URL_Dataset.csv"
df = pd.read_csv(csv, encoding="utf-8-sig", usecols=["URL", "label"])
df["is_phishing"] = (df["label"] == 0).astype(int)
X = pd.DataFrame(extract_rows(df["URL"].tolist()), columns=FEATURE_NAMES)
y = df["is_phishing"].to_numpy()
legit = X[y == 0]   # is_phishing==0 -> legitimate

bundle = url_model._load("url_random_forest")
model = bundle["model"]
explainer = shap.TreeExplainer(model)
print(f"SHAP base value (expected P over dataset): {explainer.expected_value}")

real = {
    "google": "https://www.google.com/",
    "github": "https://github.com/",
    "example": "https://example.com/",
    "wikipedia": "https://www.wikipedia.org/wiki/Phishing",
}
for name, u in real.items():
    f = extract_features(u)
    row = pd.DataFrame([f], columns=FEATURE_NAMES)
    p = float(model.predict_proba(row)[0, 1])
    sv = explainer.shap_values(row)
    vals = sv[0] if isinstance(sv, list) else np.asarray(sv)[0]
    vals = np.asarray(vals).reshape(-1)
    print(f"\n=== {name}  P={p:.4f}")
    # percentile of each feature within legit distribution
    for feat in ["url_length", "hostname_length", "path_length", "num_subdomains",
                 "letter_ratio", "has_https", "suspicious_keyword_count"]:
        col = legit[feat].to_numpy()
        pct = (col <= f[feat]).mean() * 100
        print(f"   {feat:22} value={f[feat]:<8} legit-percentile={pct:5.1f}")
    top = np.argsort(np.abs(vals))[::-1][:6]
    print("   SHAP:", [(FEATURE_NAMES[i], round(float(vals[i]), 3)) for i in top])
