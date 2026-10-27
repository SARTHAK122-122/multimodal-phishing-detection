"""Find a host-feature schema that keeps phishing detection AND clears real
benign hosts. Evaluates several subsets against a broader real benign set."""
from __future__ import annotations
import pandas as pd, numpy as np
from app import config
from app.ml.url_features import extract_rows, FEATURE_NAMES
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score, roc_auc_score

csv = config.PROJECT_ROOT / "datasets" / "sources" / "PhiUSIIL_Phishing_URL_Dataset.csv"
df = pd.read_csv(csv, encoding="utf-8-sig", usecols=["URL", "label"]).sample(60000, random_state=1)
df["is_phishing"] = (df["label"] == 0).astype(int)
Xall = pd.DataFrame(extract_rows(df["URL"].tolist()), columns=FEATURE_NAMES)
y = df["is_phishing"].to_numpy()

real_benign = [
 "https://www.google.com/","https://github.com/","https://en.wikipedia.org/wiki/Phishing",
 "https://www.amazon.com/","https://www.microsoft.com/","https://www.apple.com/",
 "https://www.netflix.com/","https://stackoverflow.com/","https://www.bbc.com/news",
 "https://www.reddit.com/","https://mail.google.com/mail/u/0/","https://www.paypal.com/home",
 "https://www.linkedin.com/","https://www.cloudflare.com/","https://www.imdb.com/",
 "https://www.spotify.com/","https://www.quora.com/","https://www.nytimes.com/",
 "https://www.weather.com/","https://www.espn.com/","https://en.wikipedia.org/",
 "https://www.wikipedia.org/","https://duckduckgo.com/","https://www.dropbox.com/",
 "https://www.adobe.com/","https://www.salesforce.com/","https://www.oracle.com/",
 "https://www.zomato.com/","https://www.swiggy.com/","https://github.com/features",
]
real_phish = [
 "http://paypal-secure-login.verify-account.xyz/index.html","http://193.0.12.44/paypal/update/session/verify.php",
 "https://appleid-verify.confirm-account.tk/login","http://microsoft-support.security-update.ml/auth",
 "https://www.amazon.co.uk.login-verify.gq/signin","http://netflix-billing.update-session.ru/verify",
 "https://google.verify-account.com.gq/auth","https://secure-bankofamerica.confirm-identity.xyz/olb/",
 "http://89.160.20.112/support/webapps/ebayauth/signin.php","https://login.verify.session-update.top/account",
 "http://free-iphone.prize-winner.xyz/claim","https://whatsapp.verify.code-confirm.ml/",
 "http://update-your-account.suspended.click/verify","https://instagram.support.help-centre.icu/login",
 "http://5.188.206.130:8080/office/index.php","http://crypto.wallet.verify-session.bond/claim",
 "http://accounts.google.com.session-validate.ru/ServiceLogin",
]

B = pd.DataFrame(extract_rows(real_benign), columns=FEATURE_NAMES)
P = pd.DataFrame(extract_rows(real_phish), columns=FEATURE_NAMES)

def evaluate(feats, label):
    X = Xall[feats]
    Xtr,Xte,ytr,yte = train_test_split(X,y,test_size=0.2,random_state=42,stratify=y)
    m = RandomForestClassifier(n_estimators=250, random_state=42, n_jobs=-1).fit(Xtr,ytr)
    pr = m.predict(Xte); pp = m.predict_proba(Xte)[:,1]
    acc=accuracy_score(yte,pr); f1=f1_score(yte,pr); auc=roc_auc_score(yte,pp)
    bp = m.predict_proba(B[feats])[:,1]; pph = m.predict_proba(P[feats])[:,1]
    fp=int((bp>=0.5).sum()); fn=int((pph<0.5).sum())
    print(f"[{label:26}] acc={acc:.4f} f1={f1:.4f} auc={auc:.4f} | "
          f"realFP={fp}/{len(real_benign)} benignMeanP={bp.mean():.3f} phishFN={fn}/{len(real_phish)}")
    if fp: print("      FP:", [u.split('/')[2] for u in real_benign if m.predict_proba(pd.DataFrame(extract_rows([u]),columns=FEATURE_NAMES)[feats])[:,1][0]>=0.5])

no_sub = [f for f in FEATURE_NAMES if f not in ("num_subdomains","num_labels")]
no_sub_dots = [f for f in no_sub if f not in ("num_dots",)]
evaluate(FEATURE_NAMES, "host-only(16)")
evaluate(no_sub, "host minus sub/labels")
evaluate(no_sub_dots, "host minus sub/labels/dots")
