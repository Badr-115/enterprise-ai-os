# Upgrade notes — usability and observability pass

## Added

- `POST /api/datasets/demo`: creates the repository-owned `mock_data.csv` fixture as a normal persisted dataset. The endpoint accepts no path or arbitrary file input.
- `GET /api/health`: returns the service name/version, demo mode, non-secret Gemini configuration state, and declared capabilities.
- `EIOS_CORS_ORIGINS`: comma-separated explicit origins for direct cross-origin deployments. The default remains the two local development origins.
- Frontend sample-data action, API health refresh, service-state feedback, and settings/operations status based on the live health response.
- Visible export errors, keyboard focus improvements, reduced-motion support, and small-screen upload controls.

## Verification performed

- Backend tests: 34 passed.
- Python compile check: passed.
- TypeScript/TSX transpilation syntax check: passed for the modified frontend source and test files.
- Frontend typecheck, Vitest, ESLint, and Next.js production build: **not run successfully in this environment** because the available `node_modules` extraction was incomplete and package installation did not finish before the environment timeout. Run these checks in GitHub Actions or after `npm ci` in the project environment.

## Important boundaries

This is still a single-instance local demonstrator. It does not yet provide authentication, tenant isolation, data deletion/retention controls, background workers, production database migrations, or a completed independent security review. A passing health check only confirms that the API process responds; it is not a production-readiness certification.
