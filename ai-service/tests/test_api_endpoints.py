"""Boot the FastAPI app and exercise the new /analyze endpoints via TestClient."""
from __future__ import annotations
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
print("health:", c.get("/health").status_code)

r = c.post("/analyze/sms", json={"message": "Urgent! Verify your account now http://paypa1.verify.xyz/a", "sender": "X"})
print("sms:", r.status_code, r.json()["classification"], r.json()["riskLevel"])

r = c.post("/analyze/email", json={"subject": "You won", "body": "Claim your prize http://win.top/1", "sender": "x@y.z"})
print("email:", r.status_code, r.json()["classification"])

r = c.post("/analyze/website", json={"url": "https://www.python.org", "render": False})
print("website(no-render):", r.status_code, r.json()["classification"])

r = c.post("/analyze/qr", json={"filePath": "qr_phish.png"})
print("qr:", r.status_code, r.json()["classification"])

# validation: bad scheme should be refused gracefully (200 with UNKNOWN/SUSPICIOUS, not 500)
r = c.post("/analyze/website", json={"url": "javascript:alert(1)", "render": False})
print("bad-scheme:", r.status_code, r.json()["classification"], r.json()["riskLevel"])
