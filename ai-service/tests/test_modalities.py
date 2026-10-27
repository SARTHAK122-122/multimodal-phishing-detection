"""End-to-end tests for the EMAIL, SMS and QR pipelines."""
from __future__ import annotations
from app.pipelines.email import analyze_email
from app.pipelines.sms import analyze_sms
from app.pipelines.qr import analyze_qr, _find_url


def show(tag, r):
    print(f"  {tag:12} -> {r['classification']:10} {r['riskLevel']:8} score={r['riskScore']}")
    for m in r["modalities"]:
        rs = m["riskScore"]
        print(f"      {m['modality']:9} {m['status']:13} {rs if rs is not None else '-'}")
    top = sorted([e for e in r["evidence"] if e["direction"] == "risk"],
                 key=lambda e: e["severity"], reverse=True)[:2]
    for e in top:
        print(f"      ev[{e['severity']}] {e['evidenceType']}: {e['description'][:90]}")


print("### EMAIL")
show("phish", analyze_email({
    "subject": "Urgent: Your account has been suspended",
    "body": ("Dear customer, we detected unusual activity. Your account will be suspended "
             "within 24 hours. Verify your password immediately at "
             "http://paypal-secure-login.verify-account.xyz/signin to keep your account."),
    "sender": "PayPal Security <support.paypal@gmail.com>",
    "spf": "fail", "dkim": "none", "dmarc": "fail",
}))
show("benign", analyze_email({
    "subject": "Your KIT's exam timetable is ready",
    "body": ("Hello, your backlog practical exam timetable for June 2026 is now available "
             "on the student portal. Please check the LMS for details. Regards, Exam Cell"),
    "sender": "Exam Cell <exam@kitt.edu.in>",
    "spf": "pass", "dkim": "pass", "dmarc": "pass",
}))

print("\n### SMS")
show("scam", analyze_sms({
    "message": ("URGENT: Your bank account has been suspended due to suspicious activity. "
                "Verify your OTP and card details immediately at "
                "http://secure-bankofamerica.confirm-identity.xyz/olb/ or lose access."),
    "sender": "VM-HDFCBK",
}))
show("benign", analyze_sms({
    "message": "Your Amazon order (OD339XX) has been delivered. Thank you for shopping with us.",
    "sender": "AMZNIN",
}))

print("\n### QR payload routing")
for p in ["https://paypal-secure-login.verify-account.xyz/login", "WIFI:S:MyNet;T:WPA;P:xx;;",
          "Congratulations you won a cash prize, call now"]:
    print(f"  '{p[:45]}' -> url='{_find_url(p)[:50]}'")

print("\n### QR decode (generate a test QR if possible)")
try:
    import qrcode  # type: ignore
    img = qrcode.make("https://appleid-verify.confirm-account.tk/login")
    from app import config
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    p = config.UPLOAD_DIR / "test_qr.png"
    img.save(p)
    show("qr-phish", analyze_qr("test_qr.png"))
except Exception as e:
    print(f"  (qrcode lib unavailable: {e}; testing decode-failure path)")
    from app import config
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    # a plain image with no QR -> graceful failure
    from PIL import Image
    p = config.UPLOAD_DIR / "test_noqr.png"
    Image.new("RGB", (200, 200), "white").save(p)
    r = analyze_qr("test_noqr.png")
    print(f"  noqr -> {r['classification']} status={r['status']} err={r.get('error')}")
