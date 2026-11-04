# Enterprise Intelligence OS — public portfolio demo

Evidence-first analytics demo for CSV/XLSX operational data, built with FastAPI + pandas and a Next.js/React dashboard. It computes deterministic KPIs, validates input data, records provenance, and produces reviewable reports. An optional LLM summarizes verified findings; it does not calculate the KPIs.

> **Status:** local demonstration, **not** a production SaaS. There is no user authentication, tenant isolation, production database, or proven public deployment. Please do not upload sensitive or personal data.

## Source layout

The runnable application is in [`enterprise-intelligence-os-main/`](./enterprise-intelligence-os-main/). The archive at the repository root is a historical snapshot, not the primary source for changes. The GitHub Actions workflow at [`.github/workflows/ci.yml`](./.github/workflows/ci.yml) intentionally targets the nested source directory.

## Run the demo

Requires Python 3.12 and Node.js 22. In separate terminals:

```bash
cd enterprise-intelligence-os-main
python -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

```bash
cd enterprise-intelligence-os-main/frontend
npm ci
npm run dev
```

Open `http://localhost:3000`, upload sample CSV/XLSX data and inspect quality checks, KPIs, and the analysis trace. Use provided demo data rather than private business records.

## Verify

```bash
cd enterprise-intelligence-os-main/backend
python -m pytest -q
cd ../frontend
npm ci && npm run lint && npm run typecheck && npm test && npm run build
```

The CI workflow runs these checks on GitHub. Its completion status must be verified on the exact commit before claiming the checks passed.

## Architecture and limitations

See [the detailed README](./enterprise-intelligence-os-main/README.md) and [architecture notes](./enterprise-intelligence-os-main/docs/ARCHITECTURE.md). The system uses a bounded, mostly deterministic local workflow; optional Gemini output is narrative context, not independently verified AI prediction. SQLite storage is local-demo only. Production use would require authentication, access isolation, request rate limiting, data retention controls, workers, backups and deployment tests.

**Evidence:** code and tests are public for reviewer inspection; the repository does not claim validated financial predictions or production traffic.
