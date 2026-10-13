# Changelog

## Interview-ready hardening

- Reworked the analysis workflow into readable, typed, documented stages.
- Added deterministic context for negative gross margin, data-quality findings, and anomaly interpretation.
- Hardened the optional Gemini prompt boundary and made provider failure non-fatal to deterministic reporting.
- Strengthened verification to reject missing/non-finite core KPI values while allowing an undefined margin rate for zero revenue.
- Added workflow regression tests for evidence references, negative-margin context, outlier caveats, and invalid metrics.
- Added least-privilege GitHub Actions quality gates for backend and frontend checks.
- Rewrote the README around quick start, architecture, analytical boundaries, and production gaps.
- Added a security policy and a five-minute interview demo runbook.

## Auditable tool-runtime upgrade

- Added an explicit allowlist of deterministic, read-only analytics tools for dataset profiling, profitability checks, quality audits, anomaly review, and categorical revenue breakdowns.
- Exposed tool outcomes, structured evidence, success state, and execution duration in task responses.
- Added an operations-view trace so tool execution can be inspected during a live technical interview.
- Connected the analysis request field to the workflow prompt rather than always sending a fixed prompt.
- Added unit and API regression coverage for tool selection, category aggregation, negative-margin signals, and prompt attempts to request unregistered capabilities.
- Documented architecture decisions and the explicit boundary between rule-based tool selection and autonomous planning.

## Product usability and service observability

- Added a server-owned sample sales dataset flow so a reviewer can exercise the full product without preparing a CSV/XLSX file.
- Added a health/capabilities endpoint that reports service version, deterministic analysis support, export support, and whether Gemini is configured without exposing credentials.
- Added a configurable, explicit CORS origin allowlist for direct cross-origin deployments.
- Connected the top-bar refresh action, Operations view, and Settings view to real API health and dataset/task refreshes instead of static status labels.
- Added visible success feedback for refresh/sample-data actions and visible error feedback when question export fails.
- Improved small-screen upload actions, focus visibility, reduced-motion handling, and navigation accessibility.
- Added regression coverage for the demo dataset workflow, health response contract, and default CORS policy.
