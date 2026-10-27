"""End-to-end WEBSITE analysis pipeline.

Orchestrates every branch for one URL and produces a single, structured,
explainable result that the FastAPI route returns and Spring Boot persists:

    validate+fetch ─┬─> HTML/DOM ─> rule score        (HTML)
                    ├─> visible text ─> lexicon score (NLP)
                    └─> render (screenshot+DOM) ─> vision (MODEL_MISSING until CNN)
    URL string ──────────────────────────────> RF/XGBoost (ML)
    forms/links/redirects ───────────────────> rule score (FORM_LINK)
                                │
                                ▼
                    weighted fusion + risk engine ─> verdict + evidence

Design notes
------------
* Fetching and rendering are **independent** branches: a render failure (no
  Chromium, a JS-heavy timeout) never blocks the URL/HTML/text modalities.
* The screenshot is captured for the UI even though the vision CNN is not yet
  trained; the VISION modality is honestly marked ``MODEL_MISSING``.
* Every modality that could not run is listed in ``missingModalities``; the
  risk engine renormalises weights over the modalities that DID run.
"""

from __future__ import annotations

import json
import time
from typing import Dict, List, Optional

from app.acquisition import fetcher, renderer
from app.acquisition.url_safety import validate_url_for_fetch
from app.features import html_features, page_text
from app.models import url_model
from app.findings import Finding
from app.risk import engine, rulescores
from app.risk.engine import ModalityOutcome


def _json(obj) -> str:
    try:
        return json.dumps(obj, default=str)[:20000]
    except (TypeError, ValueError):
        return "{}"


def _modality_score_label(score: Optional[float]) -> str:
    return engine.classify_score(score) if score is not None else engine.CLASS_UNKNOWN


def analyze_website(url: str, *, fetch: bool = True, render: bool = True,
                    max_fetch_bytes: Optional[int] = None) -> Dict:
    """Run the full multimodal website analysis. Never raises.

    Returns a JSON-serialisable dict with the verdict, per-modality outputs,
    evidence, screenshot reference, missing modalities and timing.
    """
    started = time.monotonic()
    all_findings: List[Finding] = []
    outcomes: List[ModalityOutcome] = []

    # --- 0. validate ------------------------------------------------------
    verdict = validate_url_for_fetch(url)
    if not verdict.safe:
        # Cannot even fetch: score the URL string alone (host features still
        # work without network), and mark the page-based modalities as failed.
        url_pred = url_model.predict(url)
        url_score = url_pred.probability if url_pred.ok else None
        if url_score is not None:
            outcomes.append(ModalityOutcome(
                modality="URL", status=engine.STATUS_OK, risk_score=url_score,
                prediction=_modality_score_label(url_score),
                model_name="+".join(url_pred.models_used), model_type="ML",
                detail_json=_json({"perModel": url_pred.per_model,
                                   "contributors": url_pred.contributors}),
            ))
        all_findings.append(Finding(
            modality="URL", evidence_type=f"url_blocked_{verdict.reason}",
            description=(f"The URL was refused for fetching: {verdict.detail} A URL that "
                         "fails safety validation is never treated as clean."),
            severity="CRITICAL", supporting_value=url[:200], direction="risk",
        ))
        for m in ("HTML", "NLP", "VISION", "FORM_LINK"):
            outcomes.append(ModalityOutcome(
                modality=m, status=engine.STATUS_SKIPPED,
                note="URL failed safety validation; page content was never fetched."))
        assessment = engine.assess_risk("WEBSITE", outcomes, all_findings)
        return _assemble(url, verdict.normalized or url, outcomes, all_findings,
                         assessment, started, screenshot="")

    normalized = verdict.normalized

    # --- 1. fetch HTML (independent of render) ---------------------------
    fetched = fetcher.fetch_html(normalized, max_bytes=max_fetch_bytes) \
        if fetch else fetcher.FetchResult(ok=False, reason="fetch_disabled",
                                          detail="Fetching was disabled for this scan.")
    fetched_html = fetched.html if fetched.ok else ""

    # --- 2. render (screenshot + rendered DOM + text); independent branch -
    rendered = renderer.render(normalized) if render else renderer.RenderResult(
        ok=False, reason="render_disabled", detail="Rendering was disabled for this scan.")
    screenshot = rendered.screenshot_path if rendered.ok else ""
    # Prefer the rendered DOM (JS-executed) for analysis; fall back to raw HTML.
    analysis_html = rendered.rendered_html if (rendered.ok and rendered.rendered_html) else fetched_html

    if not fetched.ok and not rendered.ok:
        all_findings.append(Finding(
            modality="URL", evidence_type="page_unreachable",
            description=(f"The page could not be fetched ({fetched.reason}) or rendered "
                         f"({rendered.reason}); only the URL was analysed. This is an "
                         "INCOMPLETE scan, not a clean one."),
            severity="INFO", direction="neutral",
        ))

    # --- 3. URL modality (ML) --------------------------------------------
    t0 = time.monotonic()
    url_pred = url_model.predict(normalized)
    url_ms = int((time.monotonic() - t0) * 1000)
    url_score = url_pred.probability if url_pred.ok else None
    if url_pred.ok:
        outcomes.append(ModalityOutcome(
            modality="URL", status=engine.STATUS_OK, risk_score=url_score,
            prediction=_modality_score_label(url_score),
            model_name="+".join(url_pred.models_used), model_type="ML",
            model_version=(url_pred.per_model[0].get("trainedAt") or "")[:19] if url_pred.per_model else "",
            detail_json=_json({"perModel": url_pred.per_model,
                               "contributors": url_pred.contributors,
                               "note": url_pred.detail}),
            processing_time_ms=url_ms,
        ))
        # Surface the strongest SHAP contributors as evidence. Only signed SHAP
        # values may claim a direction; the unsigned impurity fallback is
        # reported as neutral context, never as a risk claim.
        for c in url_pred.contributors[:4]:
            direction = c.get("direction", "neutral")
            if direction == "risk":
                severity = "MEDIUM"
                phrase = "pushed the model toward phishing"
            elif direction == "safety":
                severity = "INFO"
                phrase = "pushed the model toward legitimate"
            else:
                severity = "INFO"
                phrase = ("ranked among the most influential features "
                          "(this fallback scores influence only, not direction)")
            all_findings.append(Finding(
                modality="URL", evidence_type=f"url_feature_{c['feature']}",
                description=(f"URL feature '{c['feature']}' = {c['value']} "
                             f"{phrase}."),
                severity=severity, supporting_value=str(c["value"]), kind="INFERENCE",
                direction=direction, meta=c,
            ))
    else:
        outcomes.append(ModalityOutcome(
            modality="URL", status=engine.STATUS_MODEL_MISSING,
            note=url_pred.detail or "URL model unavailable."))
        all_findings.append(Finding(
            modality="URL", evidence_type="url_model_missing",
            description="No URL model artifact was available, so the URL was not scored.",
            severity="INFO", direction="neutral"))

    # --- 4. HTML/DOM modality (rule-based) -------------------------------
    t0 = time.monotonic()
    html_analysis = html_features.analyze_html(analysis_html, normalized) \
        if analysis_html else html_features.HtmlAnalysis(
            ok=False, detail="No HTML was available to parse.")
    html_ms = int((time.monotonic() - t0) * 1000)
    if html_analysis.ok:
        html_score = rulescores.score_html(html_analysis)
        outcomes.append(ModalityOutcome(
            modality="HTML", status=engine.STATUS_OK, risk_score=html_score,
            prediction=_modality_score_label(html_score),
            model_name="dom_rule_scorer", model_type="RULE_BASED",
            detail_json=_json(html_analysis.as_evidence()),
            processing_time_ms=html_ms,
        ))
        all_findings.extend(html_analysis.findings)
    else:
        outcomes.append(ModalityOutcome(
            modality="HTML", status=engine.STATUS_FAILED, note=html_analysis.detail))

    # --- 5. NLP modality (page text lexicon) -----------------------------
    t0 = time.monotonic()
    if rendered.ok and rendered.visible_text.strip():
        text_src = rendered.visible_text
        text_note = "rendered visible text"
    elif fetched.ok:
        text_src = page_text.extract_visible_text(fetched_html)
        text_note = "visible text from fetched HTML"
    else:
        text_src, text_note = "", "no text source"
    text_analysis = page_text.analyze_text(text_src, source="webpage") if text_src else \
        page_text.TextAnalysis(ok=False, detail=f"No visible text ({text_note}).")
    nlp_ms = int((time.monotonic() - t0) * 1000)
    if text_analysis.ok:
        nlp_score = rulescores.score_text(text_analysis)
        outcomes.append(ModalityOutcome(
            modality="NLP", status=engine.STATUS_OK, risk_score=nlp_score,
            prediction=_modality_score_label(nlp_score),
            model_name="lexicon_rule_scorer", model_type="RULE_BASED",
            detail_json=_json(text_analysis.as_evidence()),
            processing_time_ms=nlp_ms,
        ))
        all_findings.extend(text_analysis.findings)
    else:
        outcomes.append(ModalityOutcome(
            modality="NLP", status=engine.STATUS_FAILED, note=text_analysis.detail))

    # --- 6. VISION modality (screenshot captured; CNN not yet trained) ---
    if rendered.ok and screenshot:
        outcomes.append(ModalityOutcome(
            modality="VISION", status=engine.STATUS_MODEL_MISSING,
            note=("A screenshot was captured for review, but the phishing vision CNN is "
                  "not trained yet, so no visual verdict is issued. The screenshot is "
                  "shown as evidence only."),
            detail_json=_json({"screenshot": screenshot,
                               "consoleErrors": rendered.console_errors,
                               "blockedRequests": rendered.blocked_requests}),
        ))
    else:
        outcomes.append(ModalityOutcome(
            modality="VISION", status=engine.STATUS_FAILED,
            note=rendered.detail or f"Rendering failed ({rendered.reason})."))

    # --- 7. FORM_LINK modality (rule-based over forms/links/redirects) ---
    if html_analysis.ok:
        fl_score = rulescores.score_forms_links(html_analysis,
                                                redirect_count=len(fetched.redirect_chain))
        outcomes.append(ModalityOutcome(
            modality="FORM_LINK", status=engine.STATUS_OK, risk_score=fl_score,
            prediction=_modality_score_label(fl_score),
            model_name="form_link_rule_scorer", model_type="RULE_BASED",
            detail_json=_json({"forms": html_analysis.forms,
                               "externalLinks": html_analysis.links_sample[:15],
                               "redirectChain": fetched.redirect_chain}),
        ))
    else:
        outcomes.append(ModalityOutcome(
            modality="FORM_LINK", status=engine.STATUS_FAILED,
            note="No DOM available to analyse forms/links."))

    # --- 8. fusion + risk ------------------------------------------------
    assessment = engine.assess_risk("WEBSITE", outcomes, all_findings)
    return _assemble(url, normalized, outcomes, all_findings, assessment, started,
                     screenshot=screenshot, fetch=fetch, rendered=rendered,
                     fetched=fetched)


def _assemble(submitted: str, normalized: str, outcomes, findings, assessment,
              started: float, screenshot: str = "", fetch=None, rendered=None,
              fetched=None) -> Dict:
    """Build the final JSON-serialisable result shared by the API and the DB."""
    elapsed_ms = int((time.monotonic() - started) * 1000)

    # Deterministic redaction: never echo an entire email/SMS body; the URL is
    # already bounded. Keep it verbatim (it IS the input under test).
    modalities = []
    for m in outcomes:
        modalities.append({
            "modality": m.modality,
            "status": m.status,
            "prediction": m.prediction,
            "riskScore": m.risk_score,
            "modelName": m.model_name,
            "modelVersion": m.model_version,
            "modelType": m.model_type,
            "detail": json.loads(m.detail_json) if m.detail_json else {},
            "processingTimeMs": m.processing_time_ms,
            "note": m.note,
        })

    evidence = [f.as_dict() for f in findings]

    result = {
        "inputType": "WEBSITE",
        "submittedInput": submitted[:2000],
        "normalizedInput": normalized[:2000],
        "status": assessment.scan_status,
        "classification": assessment.classification,
        "riskLevel": assessment.risk_level,
        "riskScore": assessment.risk_score,
        "explanation": assessment.explanation,
        "caveats": assessment.caveats,
        "weightsUsed": assessment.weights_used,
        "evidenceModifier": assessment.evidence_modifier,
        "missingModalities": assessment.missing_modalities,
        "modalities": modalities,
        "evidence": evidence,
        "screenshot": screenshot,
        "processingTimeMs": elapsed_ms,
    }
    if fetched is not None:
        result["fetch"] = fetched.as_evidence()
    if rendered is not None:
        result["render"] = {
            "ok": rendered.ok,
            "finalUrl": rendered.final_url,
            "blockedRequests": rendered.blocked_requests[:10],
            "consoleErrors": rendered.console_errors[:10],
        }
    return result
