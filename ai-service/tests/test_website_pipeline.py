"""End-to-end test of the WEBSITE pipeline against real inputs."""
from __future__ import annotations
import json
from app.pipelines.website import analyze_website


def show(title, r):
    print(f"\n===== {title}")
    print(f"  status={r['status']}  class={r['classification']}  "
          f"risk={r['riskLevel']}  score={r['riskScore']}")
    print(f"  missing={r['missingModalities']}  time={r['processingTimeMs']}ms")
    for m in r["modalities"]:
        rs = m['riskScore']
        print(f"    {m['modality']:9} {m['status']:13} score={rs if rs is not None else '-':<7} "
              f"{m.get('modelType','')}")
    if r.get("screenshot"):
        print(f"  screenshot: {r['screenshot'].split(chr(92))[-1]}")
    print(f"  explanation: {r['explanation'][:200]}")
    top = sorted([e for e in r['evidence'] if e['direction']=='risk'],
                 key=lambda e: e['severity'], reverse=True)[:3]
    for e in top:
        print(f"    evidence[{e['severity']}] {e['evidenceType']}: {e['description'][:110]}")


print("### case 1: benign real site (full pipeline)")
show("example.com", analyze_website("https://example.com"))

print("\n### case 2: phishing-pattern URL (unresolvable host -> URL-only)")
show("paypal-verify.xyz", analyze_website("http://paypal-secure-login.verify-account.xyz/login"))

print("\n### case 3: blocked internal IP")
show("169.254.169.254", analyze_website("http://169.254.169.254/latest/meta-data/"))
