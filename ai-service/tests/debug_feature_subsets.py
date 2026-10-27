"""Confirm the PhiUSIIL legit-class artifact and test whether HOST-only features
still separate the dataset while generalizing to real benign URLs."""
from __future__ import annotations
import pandas as pd, numpy as np
from app import config
from app.ml.url_features import extract_rows, FEATURE_NAMES
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score

csv = config.PROJECT_ROOT / "datasets" / "sources" / "PhiUSIIL_Phishing_URL_Dataset.csv"
df = pd.read_csv(csv, encoding="utf-8-sig", usecols=["URL", "label"]).sample(60000, random_state=1)
df["is_phishing"] = (df["label"] == 0).astype(int)
X = pd.DataFrame(extract_rows(df["URL"].tolist()), columns=FEATURE_NAMES)
y = df["is_phishing"].to_numpy()

# Confirm artifact: fraction of legit URLs with any path/query/digit
legit = X[y == 0]
print("PhiUSIIL LEGIT class artifact check (n=%d):" % len(legit))
for f in ["path_length", "num_question_marks", "num_equals", "digit_ratio", "path_depth"]:
    frac_nonzero = (legit[f] > 0).mean()
    print(f"  {f:22} fraction>0 = {frac_nonzero:.6f}")
phish = X[y == 1]
print("PHISHING class (n=%d):" % len(phish))
for f in ["path_length", "num_question_marks", "digit_ratio"]:
    frac_nonzero = (phish[f] > 0).mean()
    print(f"  {f:22} fraction>0 = {frac_nonzero:.6f}")

# Feature subsets to compare
host_only = ["hostname_length", "num_dots", "num_hyphens", "num_subdomains",
             "has_ip_host", "has_https", "num_at_symbols", "tld_length",
             "is_suspicious_tld", "is_common_tld", "has_punycode",
             "host_digit_count", "host_entropy", "brand_in_unrelated_domain",
             "is_shortener", "num_labels"]
no_path = [f for f in FEATURE_NAMES if f not in
           ("path_length", "path_depth", "path_entropy", "num_question_marks",
            "num_equals", "num_percent_signs", "digit_ratio", "num_query_params")]

real_benign = [
    "https://www.google.com/", "https://github.com/", "https://en.wikipedia.org/wiki/Phishing",
    "https://www.amazon.com/", "https://www.microsoft.com/", "https://www.apple.com/",
    "https://www.netflix.com/", "https://stackoverflow.com/", "https://www.bbc.com/news",
    "https://www.reddit.com/", "https://mail.google.com/mail/u/0/", "https://www.paypal.com/home",
    "https://www.linkedin.com/", "https://www.cloudflare.com/", "https://www.imdb.com/",
]
real_phish = [
    "http://paypal-secure-login.verify-account.xyz/index.html",
    "http://193.0.12.44/paypal/update/session/verify.php",
    "https://appleid-verify.confirm-account.tk/login",
    "http://microsoft-support.security-update.ml/auth",
    "https://www.amazon.co.uk.login-verify.gq/signin",
    "http://free-iphone.prize-winner.xyz/claim",
    "https://whatsapp.verify.code-confirm.ml/",
    "http://5.188.206.130:8080/office/index.php",
]
for name, feats in [("FULL(30)", FEATURE_NAMES), ("HOST-ONLY", host_only), ("NO-PATH", no_path)]:
    Xs = X[feats]
    Xtr, Xte, ytr, yte = train_test_split(Xs, y, test_size=0.2, random_state=42, stratify=y)
    m = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
    m.fit(Xtr, ytr)
    acc = accuracy_score(yte, m.predict(Xte)); f1 = f1_score(yte, m.predict(Xte))
    # sanity: benign must be low, phishing high
    b = m.predict_proba(pd.DataFrame(extract_rows(real_benign), columns=FEATURE_NAMES)[feats])[:,1]
    p = m.predict_proba(pd.DataFrame(extract_rows(real_phish), columns=FEATURE_NAMES)[feats])[:,1]
    fp = int((b >= 0.5).sum()); fn = int((p < 0.5).sum())
    print(f"\n[{name}] holdout acc={acc:.4f} f1={f1:.4f} | sanity FP={fp}/15 benign  FN={fn}/8 phish  "
          f"benign_meanP={b.mean():.3f}")
