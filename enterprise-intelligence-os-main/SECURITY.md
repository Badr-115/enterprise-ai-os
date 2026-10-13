# Security policy

## Scope

Enterprise Intelligence OS is currently a local demonstration, not a production multi-tenant service. Do not upload confidential, personal, regulated, or customer-identifying data to a publicly accessible deployment.

## Reporting a vulnerability

Please do not open a public issue containing an exploit or sensitive data. Contact the repository owner privately with a minimal reproduction, affected component, impact, and suggested mitigation.

## Current security boundaries

- Uploads are size-bounded and parsed through a temporary file; file extensions and schema are validated.
- Provider credentials belong in server-side environment variables and must never be committed or sent to the browser.
- The application currently has no user authentication, tenant isolation, or request rate limiting. A public deployment must be protected until these are implemented.
- SQLite storage is intended for a single-instance demo. Backups, retention, access control, and deletion procedures must be designed before storing sensitive data.
- Treat generated narratives as suggestions, not authoritative decisions. Verify all material claims against source evidence.

## Before production

1. Add authentication, authorization, and tenant-scoped data access.
2. Add rate limits, abuse controls, secure deployment headers, and dependency/security scanning.
3. Define data retention and deletion, encrypted backups, and secret rotation.
4. Review file parsing and export paths with security tests.
5. Run threat modeling and an independent security assessment.
