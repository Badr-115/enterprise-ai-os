# Enterprise Intelligence OS

**Evidence-first business intelligence for operational data.** This repository is an interview-ready local demonstrator that turns CSV/XLSX files into deterministic KPIs, data-quality findings, source-linked analysis, and executive reports. The interface is Arabic-first and RTL-aware.

> **Honest status:** this is a local demonstration, not a production multi-tenant service. The workflow is bounded and primarily deterministic; Gemini is optional and only adds narrative context. Authentication, tenant isolation, rate limiting, and production-grade storage are not implemented.

## What it demonstrates

- **Data ingestion:** bounded CSV/XLSX uploads, column normalization, Arabic column aliases and Arabic-Indic numeral normalization.
- **Deterministic analytics:** revenue, cost, units, gross margin, margin rate, daily revenue, and IQR-based outlier signals.
- **Data quality:** missing values, invalid values/dates, duplicates, inconsistent category labels, and schema observations.
- **Evidence-first questions:** supported questions return calculations, assumptions, limitations, and bounded row evidence; unsupported requests are identified rather than guessed.
- **Observable workflow:** bounded stages for business findings, risk signals, verification, and executive reporting. A read-only tool registry executes deterministic profiling, profitability checks, quality audits, anomaly review, and category breakdowns; tool outputs are returned as structured trace data.
- **Optional LLM:** Gemini can summarize supplied facts; it is not the source of KPI calculations.
- **Persistence and exports:** SQLite-backed dataset/task/question history and self-contained HTML reports.
- **Engineering quality:** typed frontend API client, Pydantic contracts, backend and frontend regression tests, health checks, explicit CORS configuration, and GitHub Actions quality gates.

## Quick start

Requirements: Python 3.11+ and Node.js 22 recommended.

### 1. Start the backend

```bash
python -m venv .venv
# macOS/Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Start the frontend in a second terminal

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:3000`, upload `demo.csv`, review data quality, run an analysis, and export a report. The Next.js rewrite proxies `/api/*` to `http://127.0.0.1:8000` by default. To use another backend URL, set `BACKEND_API_URL` in the frontend environment before starting Next.js. The workspace also offers a **Try sample data** action that creates a repository-owned 25-row sales dataset through a fixed server endpoint; it never accepts a client-supplied filesystem path. For direct cross-origin API access, set `EIOS_CORS_ORIGINS` to a comma-separated allowlist of exact trusted frontend origins.

### GitHub Codespaces

Run the backend on port 8000 and the frontend on port 3000. Open the forwarded frontend port in the browser. Keep the backend port private; the frontend proxy reaches it inside the Codespace. Do not expose a demo containing sensitive data publicly.

## Optional Gemini narrative

Set `GEMINI_API_KEY` in the backend process environment. Optionally set `GEMINI_MODEL` to a supported model ID. Never prefix these variables with `NEXT_PUBLIC_`, place them in frontend code, or commit real credentials. Without a key, deterministic analysis remains available.

## Verification

```bash
# Backend
cd backend
python -m pytest -q

# Frontend
cd ../frontend
npm ci
npm run lint
npm run typecheck
npm test
npm run build
```

GitHub Actions runs these checks for pushes and pull requests. A green workflow proves that the configured checks passed; it does not replace browser testing, security review, or deployment verification.

## Architecture

```text
Browser (Next.js / React)
        │ typed same-origin /api client
        ▼
Next.js API rewrite ───────────────► FastAPI
                                         │
                    ┌────────────────────┼────────────────────┐
                    ▼                    ▼                    ▼
             pandas analytics     bounded workflow       SQLite store
                    │                    │
                    ▼                    ▼
             KPI + provenance    verification + report
                                         │
                                  optional Gemini text
```

- `frontend/app/page.tsx`: Arabic-first dashboard and workspace.
- `frontend/lib/api.ts`: typed browser API calls.
- `backend/app/main.py`: API, request validation, error translation, health/capability checks, CORS allowlist, sample dataset creation, and exports.
- `backend/app/services/analytics.py`: file parsing, KPI calculation, quality checks, and outlier signals.
- `backend/app/services/questions.py`: supported deterministic question intents and evidence.
- `backend/app/agents/workflow.py`: bounded stages, deterministic findings, optional provider narrative, and verification.
- `backend/app/agents/tools.py`: explicit allowlist of read-only tools with structured, deterministic outputs. The prompt can select from registered tools but cannot supply executable code or expand the allowlist.
- `backend/app/providers/`: provider adapters.
- `backend/app/db/store.py`: local SQLite persistence and idempotency.
- `backend/tests/`: API and workflow regression tests.

## Important analytical boundaries

- Upload limit: 5 MiB; row limit: 10,000; accepted formats: CSV and XLSX.
- Required columns: `date`, `revenue`, `cost`, `units` (Arabic aliases are supported).
- Outliers use the 1.5×IQR heuristic. Outlier status does not prove an error, fraud, or business cause.
- Results summarize uploaded rows only. They do not establish causation, predict future results, or guarantee representativeness.
- LLM output is narrative, can be wrong, and must be reviewed. KPI values are calculated outside the model.
- The local SQLite store is designed for a single-instance demo, not concurrent multi-instance production deployment.
- Tool selection is currently transparent intent matching, not autonomous LLM planning. The UI exposes tool names and structured outputs so an interviewer can inspect what actually ran.

## Before production

1. Add authentication, authorization, and tenant-scoped queries for every dataset, task, question, and export.
2. Add rate limiting, abuse controls, secure headers, dependency scanning, and secret rotation.
3. Define data retention/deletion, backup encryption, recovery objectives, and audit logging.
4. Move to managed PostgreSQL and background workers if concurrency and workload justify them.
5. Add end-to-end browser tests, load tests, and independent threat modeling/security review.

See [SECURITY.md](SECURITY.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [docs/INTERVIEW_DEMO.md](docs/INTERVIEW_DEMO.md).
