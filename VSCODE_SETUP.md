# Running PhishGuard AI in VS Code

A self-contained guide for a **fresh machine**. Everything below is also covered by
`README.md` (full documentation) and `PROJECT_STATUS.md` (what is measured, what is not).

---

## 1. What is in this archive

| Folder | What it is |
|---|---|
| `frontend/` | React 19 + TypeScript + Vite dashboard (scanners, history, profile, auth pages) |
| `backend/` | Spring Boot 3 (Java 21) REST API — scan engine, accounts, PostgreSQL persistence |
| `ai-service/` | FastAPI Python 3.11 AI microservice — URL/HTML/NLP/QR models + SHAP |
| `browser-extension/` | Chrome MV3 extension (Manifest V3, anonymous scans) |
| `database/` | SQL schema, incremental migrations, demo seed data, ER diagram, demo queries |
| `datasets/` | 7 labelled datasets used for training + `sources/` raw CSVs |
| `models/` | **Trained model artifacts** (URL Random-Forest + XGBoost, metadata, provenance) |
| `scripts/` | One-command setup/start/stop/test scripts (PowerShell) |
| `docs/` | Dataset report (HTML + PDF) |
| `uploads/` | Scan screenshots + processed dataset exports |
| `README.md` | Full project documentation (pipeline, API, security posture, evidence rules) |
| `PROJECT_STATUS.md` | Honest build log: every metric measured or NULL, gaps listed |

Not included (rebuildable artifacts): `node_modules/`, `.venv/`, `target/`, `dist/`, logs.

---

## 2. Install once (prerequisites)

| Tool | Version | Check |
|---|---|---|
| VS Code | current | — |
| Java (Temurin/OpenJDK) | **21** | `java -version` |
| Apache Maven | 3.9.x | `mvn -v` |
| Node.js | 20+ (includes npm) | `node -v` |
| Python | **3.11** | `py -3.11 -V` |
| PostgreSQL | 15+ (17 used here) | `psql --version` |
| Google Chrome | for the extension demo | — |

Quick installs (Windows): `winget install Microsoft.OpenJDK.21`, `winget install Apache.Maven`,
`winget install OpenJS.NodeJS.LTS`, `winget install --id Python.Python.3.11`,
`winget install PostgreSQL.PostgreSQL.17`.

**VS Code extensions**: *Extension Pack for Java*, *Python* (+ *Pylance*), optional *ESLint*,
*Docker*, *PostgreSQL*.

---

## 3. One-time project setup

Open the folder: **File → Open Folder…** → select the extracted project folder.

Open a terminal (**Ctrl+`**, PowerShell). If scripts are blocked, allow them for this session:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
```

### 3.1 Database (one-time)

Start PostgreSQL (Windows service "postgresql-x64-…", or `net start postgresql-x64-17`).
The development defaults are superuser `postgres`/`postgres` and app role
`phish_app`/`change_this_password` (override by copying `.env.example` → `.env` and editing).
Then provision the database, role, schema and seed rows (safe to re-run):

```powershell
.\scripts\setup-database.ps1
```

### 3.2 Frontend dependencies (one-time)

```powershell
cd frontend
npm install
cd ..
```

### 3.3 AI-service dependencies (one-time)

```powershell
cd ai-service
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd ..
```

(The backend needs no manual step — Maven downloads everything on first start.
PyTorch/Transformers stay commented out in `requirements.txt`; the vision CNN reports
`MODEL_MISSING` by design and the pipeline continues with the other modalities.)

---

## 4. Run the project

### Option A — everything at once

```powershell
.\scripts\start-all.ps1     # AI service + backend + dashboard, detached
```

Open **http://localhost:5173**. Stop with `.\scripts\stop-all.ps1` (PostgreSQL keeps running).

### Option B — one service per VS Code terminal (best while developing)

```powershell
# Terminal 1 — AI service (http://127.0.0.1:8000, docs at /docs)
.\scripts\start-ai-service.ps1

# Terminal 2 — Spring Boot API (http://localhost:8088)
.\scripts\start-backend.ps1

# Terminal 3 — Vite dev server (http://localhost:5173)
.\scripts\start-frontend.ps1
```

First backend start takes ~45–60 s (Maven compile + Flyway migrations).
Logs: `logs\ai-service.log`, `logs\frontend.log`, `backend\spring-boot.log`.

| Service | URL |
|---|---|
| Dashboard | http://localhost:5173 |
| REST API | http://localhost:8088/api |
| AI service | http://127.0.0.1:8000/docs |
| PostgreSQL | localhost:5432 |

### Option C — Docker (optional)

```powershell
docker compose up --build
```

---

## 5. First walk-through (demo script)

1. Open http://localhost:5173 → redirected to **Create account**.
   On a fresh database the **first account you register becomes the administrator**
   (a yellow banner confirms it); every later account is a standard user.
2. Sidebar → **Website / Email / SMS / QR** scanner → run a scan → open it in **Scan history**
   (risk score, fused weights used, evidence, SHAP contributors for URL scans).
3. **Profile** → edit display name, change password, sign out. Sign in again —
   the session cookie lasts 8 h (in-memory: a backend restart signs you out).
4. A second registered account sees the same *anonymous* scans but not the first
   account's private scans — sign in/out in two windows to demo ownership.
5. **Chrome extension**: `chrome://extensions` → Developer mode → **Load unpacked** →
   select the `browser-extension/` folder. It scans anonymously (no account needed).

---

## 6. Run the tests

```powershell
# Backend — JUnit (42 tests)
cd backend
mvn test
cd ..

# AI service — pytest (services must NOT need to be running)
cd ai-service
..\ai-service\.venv\Scripts\python.exe -m pytest tests -q
cd ..
```

---

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| `'setup-database.ps1' … blocked from running` | `Set-ExecutionPolicy -Scope Process Bypass` in that terminal |
| `mvn` not recognized | Install Maven (`winget install Apache.Maven`) and reopen VS Code, or run from a terminal where `mvn -v` works |
| Backend: `Cannot open database` / auth failed | PostgreSQL not running, or dev creds changed — align `.env` with your superuser, re-run `setup-database.ps1` |
| `npm` slow/missing | Use npm (not pnpm/yarn); `corepack enable` only if you know you need it |
| Port already in use | `.\scripts\stop-all.ps1`; or find the holder: `Get-NetTCPConnection -LocalPort 8088 -State Listen` |
| `401 {"error":"authentication_required"}` from `/api/scans` (GET) | **Expected** when signed out — history is private; scan POSTs still work anonymously |
| Dashboard shows `SERVICE_UNAVAILABLE` | AI service not started yet (Terminal 1) — scan results would be meaningless without it, so the app refuses rather than guessing |
| Everyone signed out after a while | Sessions are in-memory by design — sign in again |
| Screenshot module says `MODEL_MISSING` | Expected: no vision CNN weights are shipped; honest NULL, other modules still run |
| Seeded rows' screenshot/dataset paths point to the original machine | Cosmetic: run fresh scans on the new machine for new evidence |

---

## 8. Honesty rules (project-wide)

Every metric in this project is either **measured** or reported as **NULL/NOT_TRAINED** —
no mocked results, no fabricated accuracy, no "clean" verdict on failed analysis.
Read `README.md` § *Evidence and safety rules* and `PROJECT_STATUS.md` before changing code,
and keep every new feature compliant with that contract.
