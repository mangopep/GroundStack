# Security testing status

No application-level security regression suite exists for authentication, tenant isolation, path traversal, archive/PDF resource exhaustion, prompt injection, secrets, or cross-store deletion. The exact hashed dependency lock passes local `pip-audit` with no known vulnerabilities. Gitleaks and CodeQL are configured but have not yet run on this change in GitHub Actions. Container scanning, SBOM/license checks, and dependency provenance are not configured for GroundStack.

Future tests should include malformed/oversized PDFs, path and filename edge cases, authorization at index/query boundaries, prompt injection in retrieved passages, secret leakage in logs, and vulnerability scans of Python dependencies and pinned container images.
