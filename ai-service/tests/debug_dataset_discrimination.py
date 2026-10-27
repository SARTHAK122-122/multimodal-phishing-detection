"""Decisive diagnostic: does the loaded model still discriminate on ITS OWN
dataset? If yes -> real-world URLs are out-of-distribution for these 16
features. If no -> a load/label bug. Also probes the raw PhiUSIIL feature
relationship for has_https."""
from __future__ import annotations
import pandas as pd, numpy as np, joblib
from app import config
from app.ml.url_features import extract_rows, FEATURE_NAMES
from app.models import url_model

csv = config.PROJECT_ROOT / "datasets" / "sources" / "PhiUSIIL_Phishing_URL_Dataset.csv"
df = pd.read_csv(csv, encoding="utf-8-sig", usecols=["URL", "label"]).head(4000)
df["is_phishing"] = (df["label"] == 0).astype(int)
rows = extract_rows(df["URL"].tolist())
X = pd.DataFrame(rows, columns=FEATURE_NAMES)
y = df["is_phishing"].to_numpy()

bundle = url_model._load("url_random_forest")
model = bundle["model"]
print("bundle features:", bundle.get("features") == FEATURE_NAMES)
proba = model.predict_proba(X)[:, 1]
pred = (proba >= 0.5).astype(int)
acc = (pred == y).mean()
print(f"sample accuracy on dataset head(4000): {acc:.4f}")
print(f"  predicted phishing: {pred.sum()}/{len(pred)}  actual phishing: {y.sum()}")
# confusion-ish
for cls in (0, 1):
    m = y == cls
    print(f"  actual={cls}: mean P(phishing)={proba[m].mean():.4f} n={m.sum()}")

# relationship of has_https to label in the dataset
df2 = pd.read_csv(csv, encoding="utf-8-sig", usecols=["URL", "label"]).head(4000)
df2["has_https"] = df2["URL"].str.lower().str.startswith("https://").astype(int)
print("\nhas_https x label (dataset head):")
print(pd.crosstab(df2["has_https"], df2["label"]))
