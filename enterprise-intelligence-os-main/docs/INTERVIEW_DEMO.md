# Interview demo runbook (5 minutes)

## Before the interview

1. Start the API and the frontend using the README instructions.
2. Open the frontend and confirm the API health check succeeds.
3. Upload `demo.csv`; show the source row count, calculated KPIs, and quality findings.
4. Enter a specific analysis request (for example, “Review data quality and compare revenue by region”), run the workflow, and open the report.
5. Open **تشغيل الوكلاء** and expand the tool trace to show the exact registered tools, success state, summaries, and JSON outputs. Point to each report finding’s evidence reference.
6. Ask one supported question about totals, averages, trends, or data quality; show the calculation and evidence.
7. Export the report and open it locally.
8. Have a backup screen recording or screenshots ready in case the network or demo environment fails.

## Suggested narration

- **Problem:** business teams need to turn messy operational spreadsheets into explainable decisions.
- **Approach:** FastAPI validates and analyzes source data; pandas computes metrics; a bounded workflow organizes findings; optional Gemini only adds a narrative layer.
- **Trust:** numerical claims originate from deterministic calculations, and the report exposes evidence and limitations.
- **Engineering:** typed API contracts, persistence, idempotent task submission, an explicit read-only tool allowlist, inspectable tool traces, regression tests, and CI quality gates.
- **Trade-offs:** this is a local demo, not production multi-tenancy. Authentication, tenant isolation, background jobs, rate limits, and production storage are explicit gaps.

## Questions to prepare for

- Why are KPIs computed in code rather than by the language model?
- How would you isolate tenant data and enforce authorization?
- What happens if the provider times out or returns unsupported output?
- How would you move from SQLite to PostgreSQL safely?
- How would you test analytical correctness and prevent regressions?
- Which claims are verified, and which remain hypotheses?

Never describe a planned feature as implemented. The tool registry uses transparent intent rules today; it is not yet an autonomous planning agent. Run the actual demo and explain the trade-offs clearly.


## Fast demo path

If you do not have a suitable CSV/XLSX file at the interview, open **مساحة البيانات** and choose **جرّب بيانات نموذجية**. The API creates a repository-owned sample dataset and stores it like an uploaded dataset. Then demonstrate quality findings, ask a supported business question, run the workflow, inspect tool traces in Operations, and export the report. The top-bar refresh action checks the API health endpoint and refreshes dataset/task lists.
