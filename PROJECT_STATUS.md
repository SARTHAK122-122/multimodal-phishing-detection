# PROJECT_STATUS.md

**Project:** Multimodal AI-Based Phishing Detection and Real-Time Browser Protection Platform
**Course:** B.Tech Final Year Project, A.Y. 2026-27
**Last verified:** 2026-10-11 (all statements below were re-checked on this date against the running system or the test suites)

This file is the honest state of the project. Every number here is either
measured (with how it was measured) or explicitly marked NULL/NOT DONE.
Nothing in this project fabricates a result: when a component cannot run
(missing model, unreachable service, blocked URL), it reports that fact as
`FAILED` / `MODEL_MISSING` / `PARTIAL` instead of guessing.

---

## 1. System status at a glance

| Component | State | Evidence |
|---|---|---|
| Python AI service (FastAPI, 127.0.0.1:8000) | **Running, verified** | `/health` UP; all 4 pipelines exercised via API and via Spring Boot |
| Spring Boot backend (8088) | **Running, verified** | `/api/health` reports DB UP + AI service UP; Flyway V1-V8 applied cleanly (V8 = authentication columns + seed-scan detach) |
| PostgreSQL 17 | **Running, verified** | 33 scans (31 live + 2 flagged seed rows), 151 modality rows, 129 evidence rows |
| React dashboard (5173) | **Running, verified in a real browser** | End-user navigation restructure: Dashboard (`/dashboard`) + four dedicated scanner pages (`/scan/website|email|sms|qr`) as first-class sidebar entries, shared results engine, research pages URL-only; live scans through the new pages produced website LEGITIMATE/LOW, email + SMS PHISHING/CRITICAL, QR decoded-phishing CRITICAL; History filters + full report verified; zero console errors; Lighthouse accessibility 100 / best-practices 100; production `dist` build green with same-origin `/api` |
| Chrome MV3 extension | **Code complete, not load-tested in Chrome** | manifest/background/content/popup written; icons generated; no automated browser test has been run against a live profile |
| Accounts & sessions (Spring Security) | **Running, verified end-to-end** | register → first account becomes ADMIN, login/logout, profile edit, change-password (old password rejected afterwards) all exercised in a real browser; member session → 403 on `/api/datasets`; anonymous `POST /api/scans/website` → 200 with `user_id NULL`, anonymous `GET /api/scans` → 401 JSON; storage is BCrypt hashes only |
| Docker images + compose stack | **Built and verified end-to-end** | All three images build (`docker compose build`); `docker compose up -d` → all 4 containers healthy; a real wikipedia.org scan through the nginx proxy returned LEGITIMATE/LOW with SHAP contributors intact; stack torn down cleanly |
| Backend tests (JUnit) | **42/42 pass** | `mvn test` — AuthControllerTest 14, ScanOwnershipTest 6, ScanControllerTest 14, ScanServicePersistTest 8, zero failures |
| AI-service tests (Python) | **8/8 suites exit 0** | 63 explicit checks (28+16+13+6) + 4 end-to-end demonstration suites |

---

## 2. What works end-to-end (verified, not simulated)

1. **Website/URL scanning** — URL submitted to Spring Boot → forwarded to
   FastAPI → SSRF-safe fetch (bounded, redirect re-validated) → URL-feature ML,
   DOM rules, text-NLP rules, form/link rules → weighted fusion → persisted to
   PostgreSQL with per-modality rows + evidence → rendered on the report page.
   Verified live: python.org, wikipedia.org, example.com, a live phishing-pattern
   URL, and `www.paypal.com/signin` submitted through the dashboard UI
   (scan #11, 18 s, fetch-only mode).
2. **Email scanning** — subject/body/sender/headers → NLP + embedded-URL
   analysis + metadata rules → fused verdict + evidence. Verified: benign mail
   → LEGITIMATE/LOW, urgent-credential phishing mail → PHISHING/CRITICAL.
3. **SMS scanning** — message/sender → NLP + link + metadata rules. Verified:
   bank-impersonation scam → PHISHING/CRITICAL (scan #3).
4. **QR scanning** — multipart image upload → OpenCV decode (grayscale + 2x
   upsample retry) → decoded payload analysed as a *string* (the link is never
   visited). Verified: phishing QR → PHISHING/CRITICAL score 0.853 (scan #7).
   Unreadable QR → honest `UNKNOWN` decode-failure status, never a clean verdict.
5. **Browser protection path** — extension asks the backend for each visited
   host, badges the result, and shows an interstitial on PHISHING + HIGH/CRITICAL.
   Backend failure surfaces as an `err` badge, never as "safe".
6. **Explainability** — every report shows: per-modality score/model/status,
   signed SHAP contributors for the URL models (▲ toward phishing / ▼ toward
   legitimate), the fusion weights actually used for that input type, evidence
   items with severity + direction (risk/safety/neutral) + kind
   (FINDING/INFERENCE), and explicit caveats ("riskScore is not a calibrated
   probability", "an incomplete scan is not a clean scan").
7. **Honest failure handling** — blocked URL (javascript:, file:, ftp:, loopback,
   link-local, cloud-metadata IP, userinfo-in-URL) → CRITICAL finding, score 1.0,
   never clean (6/6 verified). AI service down → HTTP 503 with a start hint.
   AI service 5xx → HTTP 502 "failed while processing" (distinct from outage).
8. **Accounts & sessions** — `POST /api/auth/register` creates the account
   (BCrypt hash; the first real account on a fresh database becomes ADMIN) and
   signs it in; login, logout, profile PATCH and change-password were all
   exercised end-to-end in a browser (wrong current password → honest 400 that
   does **not** end the session; after a password change the old one fails with
   the generic message and the new one signs in). Signed-out hits redirect to
   `/login?next=…` and land there after signing in. Research routes are closed
   twice: an honest *Administrator access required* panel in the UI and HTTP 403
   from the server for member sessions. Scan POSTs deliberately stay anonymous
   so the extension keeps working (verified: session scan → `user_id` set,
   anonymous scan → `user_id` NULL).

---

## 3. Measured results (how measured)

### URL model v3 (host-only, 16 features) — trained 2026-10-11

| Model | Hold-out accuracy | F1 | ROC-AUC |
|---|---|---|---|
| Random Forest | 0.9559 | 0.9472 | 0.9798 |
| XGBoost | 0.9583 | 0.9499 | 0.9842 |

- **Real-world sanity set** (`datasets/url_sanity_realworld.csv`, hand-labelled,
  40 URLs incl. github.com, stackoverflow.com, python.org, wikipedia.org and
  live phishing patterns): **38/40 correct, 0 phishing missed**.
  Residual false positives are benign sites the URL model alone cannot clear;
  they are resolved by content fusion in the full website pipeline.
- **Why v3 exists (dataset artifact):** 100 % of PhiUSIIL "legitimate" URLs are
  bare domains (path_length = path_depth = 0), so path-based features became a
  dataset artifact that scored ≈100 % but failed on real URLs. v1/v2 metrics are
  therefore rejected as misleading; path features were removed, costing ~4 pts
  of hold-out accuracy but restoring real-world sanity. This is the project's
  central "accuracy vs. generalisation" finding.
- Artifacts: `models/url_random_forest.joblib`, `models/url_xgboost.joblib`
  (+ metadata JSON + `url_models.training.json`).

### Fusion / detection behaviour (measured by the test suites)

- Blocked-URL suite: 6/6 refusals, all PHISHING/CRITICAL.
- Explainability suite: 16/16 (SHAP shape handling for RF's `(samples, features,
  classes)` output, direction consistency, semantic sign checks — e.g.
  `has_https` reads as *safety* on paypal.com and *risk* on a bare-http phish).
- Website core suite: 28/28 feature-extraction checks.
- End-to-end latency (local machine): fetch-only website scan ≈ 3–18 s
  depending on the target; with `render: true` (headless Chromium screenshot)
  ≈ 30–60 s (backend read timeout raised to 120 s accordingly).

---

## 4. Known gaps — explicitly NOT done (no pretending otherwise)

| Gap | State | Reason / path forward |
|---|---|---|
| **Vision CNN** | `MODEL_MISSING` | `torch`/`transformers` are intentionally not installed (Windows + size). The screenshot *is* captured and stored as evidence when `render: true`; the fusion engine renormalises over available modalities and adds a caveat. Training a small CNN over a screenshot dataset is the designed next step. |
| **NLP transformer (DistilBERT)** | Not trained | Requirements list the torch stack commented out. The NLP modality is a transparent lexicon/rule scorer (documented model name `lexicon_rule_scorer`) — honest and explainable, but not a learned model. |
| **DOM-ML model** | Not trained | HTML/DOM modality is a rules scorer (`dom_rule_scorer`) over extracted structural features; the feature pipeline exists so a trained model can replace it without schema changes. |
| **Password reset / 2FA / lockout** | Not implemented | Authentication itself exists (§7 item 10): BCrypt + server-side sessions + ADMIN/USER roles, enforced in the browser and on every protected API route. What is deliberately missing and documented rather than faked: self-service password reset (no mail service), two-factor authentication, and account lockout/brute-force throttling beyond the generic login error. Sessions are in-memory — restarting the backend signs everyone out. |
| **Extension live-browser test** | Not done | No automated Chrome profile test; manual load-unpacked instructions are in `browser-extension/README.md`. Extension JS is syntax-checked (`node --check`) and all message-passing paths reviewed. |
| **Calibration** | NULL | `riskScore` is a fused model score in [0,1], **not** a calibrated probability; this caveat is shown on every report. Isotonic/Platt calibration is future work. |
| **Scan queue / async API** | Not implemented | Scans are synchronous HTTP requests (browser extension hides latency behind its badge). A queue would be needed for scale. |

---

## 5. Data provenance (seed/synthetic flagged)

- **Live scans**: rows 3–33 in `public.scans` are real analyses performed by the
  running system (`is_seed_data = false`; 31 rows at the last count, growing).
- **Seed demo scans**: rows 1–2 were inserted by Flyway `V2__seed_demo_data.sql`
  and are flagged `is_seed_data = true` — they appear in history but are never
  mixed into any metric. Since V8 they carry `user_id IS NULL` (visible to
  signed-in users as shared device scans, not owned by the demo accounts).
- **Datasets**: 7 uploaded CSV datasets with 7 recorded preprocessing runs and
  4 evaluation runs; models are trained only on PhiUSIIL (URL) with the
  hand-labelled sanity set used exclusively for the real-world check above.
- No metric in the dashboard or this document counts synthetic rows as real.

---

## 6. How to run (local, PowerShell)

```powershell
# one-time: database + role
.\scripts\setup-database.ps1

# everything, in order, detached, with health polling - services survive
# closing the terminal (logs: logs\ai-service.log, logs\frontend.log,
# backend\spring-boot.log)
.\scripts\start-all.ps1          # dashboard http://localhost:5173

# stop everything except PostgreSQL
.\scripts\stop-all.ps1
```

Or with Docker: `docker compose up --build` → dashboard on
http://localhost:5173 (nginx proxies `/api` to the backend; the AI service and
PostgreSQL are not published outside the compose network). Note that the
containerized stack uses its **own** PostgreSQL volume, so scans made through
it do not appear in the local development database.

Tests:

```powershell
# Java (42 tests)
cd backend; mvn test

# Python (8 suites)
cd ai-service
$env:PROJECT_ROOT = (Resolve-Path ..)
.venv\Scripts\python -m tests.test_website_core        # + the other test_* modules
```

---

## 7. Recent fixes worth knowing (regression-protected)

1. **Fetcher deny-path crash** — `_deny()` raised `TypeError: got multiple
   values for 'final_url'` on any HTTP ≥ 400 response, turning a handled denial
   into an unhandled 500. Fixed and locked down by
   `tests/test_fetcher_hardening.py`.
2. **SHAP orientation** — on shap 0.46 the RandomForest explainer returns
   `(samples, features, classes)`; the old code reshaped it into a mixed
   vector, hit an IndexError (silently swallowed) and fell back to impurity
   importances for *every* scan — while the fallback itself fabricated
   `direction: "risk"` for unsigned values. Fixed (`_phishing_class_values`
   handles all three explainer shapes; the fallback now reports `neutral`
   with "influence, not direction" wording); locked down by
   `tests/test_url_explain.py` (16 checks) and visible in reports as signed
   ▲/▼ contributors.
3. **Screenshot path** — the stored reference is relativised against the real
   upload directory (`StorageService.storedImageRef()`), so
   `GET /api/scans/{id}/screenshot` streams the file (verified 200 +
   `image/png` for scans with a render, 404 for scans without one).
4. **Upstream error honesty** — Spring now distinguishes AI-service
   unavailability (503) from AI-service failure (502) instead of labelling
   every failure "not reachable".
5. **Stale model registry** — the `model_versions` rows still carried the
   *v2* metrics (accuracy 0.995 — the rejected artifact model) while the
   service actually ran v3 (0.956). The rows were re-registered from the
   saved v3 training summary (`models/url_models.training.json`, same
   measured numbers, no retraining) and the registration notes now explain
   the schema change honestly. The dashboard shows what runs.
6. **Background service starts died with the terminal** — `Start-Process`
   children inherit the launcher's console and died on shell exit (the log
   showed only `^C`); plain WMI-created `cmd` proved killable too when the
   launching shell was force-killed. The `-Background` mode now launches
   each service through `wscript.exe` (GUI subsystem: no console exists to
   tear down) running a generated hidden-launch VBScript, spawned via WMI
   (parented to the WMI service, not the shell) — see `scripts/detached.ps1`.
   Verified twice: services stayed UP after a clean launcher exit **and**
   after a deliberately force-killed foreground command. Logs:
   `logs\ai-service.log`, `logs\frontend.log`, `backend\spring-boot.log`.
7. **Docker build gotchas (both fixed in the Dockerfiles)** —
   `python:3.11-slim:latest` had moved to Debian 13 (trixie), which
   Playwright 1.49 does not recognise, so `--with-deps` fell back to Ubuntu
   20.04 package names and failed (exit 100); the base is now pinned to
   `python:3.11-slim-bookworm`. The slow uplink also killed `pip install`
   mid-download; it now runs with `--retries 10 --timeout 180` under a
   BuildKit cache mount, and Maven uses wagon retry/timeout flags. All three
   images build, and the compose stack was verified with a live scan through
   nginx.
8. **Full UI redesign (2026-10-19)** — the dashboard was a dark, developer-oriented
   interface (navy/purple, database/service panels, B.Tech sidebar footer). It is
   now a light blue/white product interface: shared design tokens in
   `frontend/src/index.css`, Lucide icons, responsive sidebar (off-canvas drawer
   below 860px), and reworked pages — Overview (hero quick-scan + honest summary
   counts + recent activity + guidance), Analyze Threat (4 plain-language tabs,
   advanced settings collapsed, honest staged progress, QR drag-and-drop +
   preview), report (verdict hero, "Why this result?" split into raised/lowered
   signs with observed-vs-prediction badges, verdict-aware next steps, technical
   details collapsed), Scan History (search + type/verdict/risk filters +
   pagination over real rows), Model Performance + Evaluation History (measured
   metrics only), System Status (user-facing availability strip; PostgreSQL /
   topology counts moved into a clearly marked developer-diagnostics disclosure
   that is honestly labeled *developer-only* — the `/health` route now requires a
   signed-in session (any role), while the `/api/health` endpoint itself stays
   public for ops/Docker healthchecks, as the page discloses).
   No API, ML, or database changes. Lighthouse: accessibility 1.00, best
   practices 1.00. Production `dist` verified via `vite preview` with the
   same-origin `/api` proxy (dev: Vite proxy; container: nginx) — the bundle no
   longer hardcodes `localhost:8088`. Also fixed a latent foreground-mode bug in
   `scripts/start-frontend.ps1` (`& $npm.cmd` → `& $npm`; the background path
   was unaffected) and removed the dead Vite-boilerplate `App.css`.
 9. **End-user navigation restructure (2026-10-19, second pass)** — per the product
    spec, the generic *Analyze Threat* tab menu is gone: each scanner is now a
    first-class sidebar destination with its own route and page — MAIN (Dashboard
    `/dashboard`), THREAT DETECTION (`/scan/website`, `/scan/email`, `/scan/sms`,
    `/scan/qr`), MY ACTIVITY (Scan History). Research pages (Dataset & Training,
    Model Performance, Evaluations, System Status) remain fully functional but are
    routed URL-only, out of the user navigation — and since the authentication
    pass they are role-gated as well: an honest *Administrator access required*
    panel in the UI, and HTTP 403 from the server for member sessions. New shared results engine (`components/scanner/shared.tsx` +
    `ScanResultCard.tsx` + `useScanner.ts`) renders one verdict hero / evidence /
    next-steps language across all four scanners and accepts both live and stored
    shapes; the Dashboard leads with the four feature cards + real totals + recent
    five + scanner-linked empty state. Verified live in the browser: website scan
    (wikipedia.org → Likely Legitimate/LOW, 8.3 s), email scan (→ Phishing
    Detected/CRITICAL 90%, 8 evidence items, links panel), SMS scan (→ CRITICAL
    100%), QR scan (stored phishing QR injected via drop → decoded
    `appleid-verify.confirm-account.tk`, CRITICAL, "never visited" note), full
    report route, History filters (PHISHING → 13 real matches), legacy
    `/analyze` → `/dashboard` redirect, research routes rendering outside the nav,
    zero console errors, production build green (401 KB JS, no hardcoded host in
    `dist`). Dead code from the pass (unused hook API, hidden icon) removed.
11. **Authentication, profile and auth-page redesign (2026-10-19, third pass)** —
    real authentication end to end: Spring Security filter chain (BCrypt,
    server-side 8-hour sessions in an HttpOnly SameSite=Lax cookie, JSON
    401 `authentication_required` / 403 `forbidden` entry points, CSRF disabled
    with written justification in `SecurityConfig` — JSON-only API + SameSite
    cookie), Flyway `V8__authentication.sql` (adds `display_name` /
    `last_login_at`, detaches seed scans from the demo users; V1–V7 untouched),
    first real account → ADMIN, generic login failures (no username
    enumeration), research endpoints ADMIN-only, scan POSTs + `/api/health`
    permitAll so the Chrome extension and curl/demo scripts stay anonymous
    (verified: session scan → `user_id` set, anonymous scan → `user_id` NULL,
    anonymous `GET /api/scans` → 401 JSON). Read-visibility rule: own scans +
    unattributed scans; another account's row → 404 (not enumerable).
    Frontend: `AuthContext` + redesigned login/register pages + Profile
    (identity, edit display name/email, change password, honest "what this build
    does not have" list), `RequireAdmin` panels, sidebar account chip, axios 401
    interceptor (excludes `/auth/*`, preserves `?next=`), and a deterministic
    post-login landing: the signed-in route table's `/login → /dashboard`
    `<Navigate>` effect re-fired and raced an effect-based landing
    (`/history` was bounced back to `/dashboard` — diagnosed with history-API
    stack instrumentation showing the third `replaceState` came from
    react-router's Navigate, not the app), fixed by rendering a single
    `pendingLanding` `<Navigate>` and mounting no competing redirects until the
    landing is consumed. The sign-in/register pages were then redesigned per the
    UI brief: centered 444px white card on flat `#F5F8FF`, brand header,
    "Welcome back" + subtitle, uniform 42px fields — root cause of the original
    broken layout was the global form-control rule omitting
    `input[type=password]`, which rendered password boxes as unstyled 170×21
    browser defaults beside styled text fields — password visibility toggles,
    full-width button with pending state, an honest session-lifetime note in
    place of a "Remember me" checkbox the backend does not support, and the old
    "not a guarantee of safety" footer line removed (replaced by the subtle
    "AI-powered threat analysis"). Verified: 42/42 JUnit tests, production build
    green, Lighthouse accessibility/best-practices 1.00 on `/login`, first-admin
    register, member 403, change-password → old password rejected → new password
    signs in, zero JS console errors (only deliberate 400/401 network logs from
    negative tests). Still missing (documented, not faked): password reset, 2FA,
    login throttling, extension load-test in Chrome.
