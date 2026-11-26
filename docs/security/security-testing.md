# Security testing status

No application-level security regression suite exists for authentication, tenant isolation, path traversal, archive/PDF resource exhaustion, prompt injection, secrets, or cross-store deletion. The exact hashed dependency lock passes local `pip-audit` with no known vulnerabilities. Trivy initially found two high Soup Sieve advisories in a marker branch for Python 3.11.0–3.11.4; the declared Python minimum and universal lock were updated to 3.11.5, where the locked Soup Sieve version is 4.1.3. The container workflow checks source manifests and built image vulnerabilities/misconfigurations/licenses and emits a CycloneDX SBOM. The release workflow is approval-gated and must complete a successful non-publishing rehearsal before any publish configuration is enabled. No license allowlist has been approved.

GitHub Actions evidence on the prior pushed commit showed Gitleaks and CodeQL success but Python collection failed on undeclared imports; those dependencies are now locked and the repaired workflows require a new remote run. Local isolated service tests passed. Do not describe the new workflow files as GitHub-verified until the Actions runs for their commit complete.

Future tests should include malformed/oversized PDFs, path and filename edge cases, authorization at index/query boundaries, prompt injection in retrieved passages, and secret leakage in logs.

## Automated check matrix

| Gate | Pull request | Push / schedule | Evidence and scope |
|---|---|---|---|
| `pip-audit` | Yes, CI | Weekly CI | Hash-locked Python dependency versions |
| Bandit | Yes, CI | Weekly CI | Python source static security checks; currently no findings |
| CodeQL | Yes | `main` push and weekly | Python and JavaScript/TypeScript; writes security findings only |
| Gitleaks | Yes | `main` push and weekly | Full Git history; no checkout credential persistence |
| Trivy filesystem | Yes, container workflow | Weekly | Python manifests (including the custom full-lock filename), secrets, vulnerabilities, and dependency visibility |
| Trivy image | Yes, container workflow | Weekly | API image vulnerabilities, Docker misconfiguration, and license inventory |
| Hadolint | Yes, container workflow | Weekly | Dockerfile lint |
| SBOM | Container workflow | Push, PR, weekly | CycloneDX image SBOM artifact retained 14 days; release SBOM included with GitHub Release |

There are currently no Terraform files or frontend package manifest, so Terraform scanners and `npm audit` are not run. The UI is plain JavaScript and is syntax-checked with Node. No temporary exception register entries exist. Maintainers have not approved a license allowlist; license inventory is reported for review rather than silently treated as approved.

### Temporary exception register

| Finding | Affected artifact | Owner | Expiry | Remediation | Status |
|---|---|---|---|---|---|
| None | — | — | — | No scanner findings are currently excepted | Empty |
