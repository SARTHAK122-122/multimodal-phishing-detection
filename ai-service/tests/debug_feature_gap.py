"""What crude-feature pattern separates PhiUSIIL legit from phishing, and where
do real benign URLs fall? Compares class-conditional distributions."""
from __future__ import annotations
import pandas as pd, numpy as np
from app import config
from app.ml.url_features import extract_rows, FEATURE_NAMES

csv = config.PROJECT_ROOT / "datasets" / "sources" / "PhiUSIIL_Phishing_URL_Dataset.csv"
df = pd.read_csv(csv, encoding="utf-8-sig", usecols=["URL", "label"]).sample(30000, random_state=1)
df["is_phishing"] = (df["label"] == 0).astype(int)
X = pd.DataFrame(extract_rows(df["URL"].tolist()), columns=FEATURE_NAMES)
X["is_phishing"] = df["is_phishing"].to_numpy()

real_benign = [
    "https://www.google.com/", "https://github.com/", "https://en.wikipedia.org/wiki/Phishing",
    "https://www.amazon.com/", "https://www.microsoft.com/", "https://www.apple.com/",
    "https://www.netflix.com/", "https://stackoverflow.com/", "https://www.bbc.com/news",
    "https://www.reddit.com/", "https://mail.google.com/mail/u/0/", "https://www.paypal.com/home",
    "https://www.linkedin.com/", "https://www.cloudflare.com/", "https://www.imdb.com/",
]
R = pd.DataFrame(extract_rows(real_benign), columns=FEATURE_NAMES)

print(f"{'feature':24} {'phish_mean':>11} {'legit_mean':>11} {'realbenign_mean':>16}  verdict")
for f in FEATURE_NAMES:
    pm = X.loc[X.is_phishing == 1, f].mean()
    lm = X.loc[X.is_phishing == 0, f].mean()
    rm = R[f].mean()
    # which class is real benign closer to?
    closer = "phish" if abs(rm - pm) < abs(rm - lm) else "legit"
    print(f"{f:24} {pm:11.3f} {lm:11.3f} {rm:16.3f}  ->closer:{closer}")
