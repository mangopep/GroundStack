# ForgeStack engineering comparison

This is a read-only comparison of the public [mangopep/forgestack](https://github.com/mangopep/forgestack) reference and `rag_platform`, captured on 2026-11-26. It adapts patterns to this Python application; it does not copy Go-specific implementation.

## What the reference actually contains

ForgeStack is a Go service repository with a separate Python API and a documentation website. Its [`python-ci.yml`](https://github.com/mangopep/forgestack/blob/main/.github/workflows/python-ci.yml) installs a pinned requirements lock, runs Ruff and strict mypy, executes tests, scans Python dependencies, lints/scans/builds a Python image, and smoke-tests its health route as a non-root process. Its [`codeql.yml`](https://github.com/mangopep/forgestack/blob/main/.github/workflows/codeql.yml) runs Go, Python, and JavaScript/TypeScript analysis, including a schedule. Its [`secret-scan.yml`](https://github.com/mangopep/forgestack/blob/main/.github/workflows/secret-scan.yml) scans full history with a SHA-pinned Gitleaks action and checkout without persisted credentials.

Other useful patterns include least-privilege token scopes in [`ci.yml`](https://github.com/mangopep/forgestack/blob/main/.github/workflows/ci.yml), a no-push [`container-scan.yml`](https://github.com/mangopep/forgestack/blob/main/.github/workflows/container-scan.yml), explicit docs drift and Mermaid validation in [`docs-check.yml`](https://github.com/mangopep/forgestack/blob/main/.github/workflows/docs-check.yml), and a tag-only [`release.yml`](https://github.com/mangopep/forgestack/blob/main/.github/workflows/release.yml) that separates pre-publish verification from privileged publication. The release flow includes tag ancestry validation, image-version checks, SBOMs, vulnerability scans, provenance, and signing. The public [`scripts/`](https://github.com/mangopep/forgestack/tree/main/scripts) contains focused guards and fixture-backed tests rather than relying only on workflow YAML.

## Evidence from recent runs

GitHub's Actions API showed the latest returned pull-request run batch on ForgeStack's `develop` branch, created 2026-11-23, with success conclusions for CI and Quality Gates, Python/Go security analysis, secret scanning, container scanning, Terraform checks, documentation checks, branch-flow policy, and automated review. This is a snapshot of recent workflow runs, not proof that every workflow, release, or future change succeeds. See the [live Actions history](https://github.com/mangopep/forgestack/actions) for current status.

## Adaptation to GroundStack

| Pattern | ForgeStack evidence | GroundStack adaptation |
|---|---|---|
| Reproducible Python checks | Pinned requirements lock, Ruff, strict mypy, tests | A hash-locked requirements file now feeds CI. Local Ruff and source formatting pass; strict type checking remains unconfigured. The clean GitHub CI install is NOT VERIFIED yet. |
| Action supply chain | Immutable action SHAs and `persist-credentials: false` | The changed CI, security, and docs workflows now pin each action to an immutable SHA and disable checkout credentials. Existing other workflows still need review before claiming repository-wide SHA pinning. |
| Security scanning | Scheduled CodeQL, pip-audit, Gitleaks, Trivy, Hadolint | The observed `diskcache` finding was removed with unused RAGAS; the exact locked dependency audit returns no known vulnerabilities locally. CodeQL and Gitleaks are configured but their updated remote runs are NOT VERIFIED yet. |
| Container verification | Build without registry push, scan image, test non-root health | GroundStack has no application Dockerfile or complete service API. First define the smallest deployable app slice, then build and smoke-test that exact image before adding publishing. |
| Release trust | Tag ancestry and separate privileged publishing | GroundStack has no release tags, production image, or protected main branch. Do not create a publishing workflow until these are addressed; any real release still needs explicit approval. |
| Documentation | Generated-doc drift check, relative-link and Mermaid validation | Strict Zensical builds now catch broken local links and navigation. Add dedicated Mermaid syntax and source-reference drift checks as follow-up gates. |
| Governance | Multiple branches/rulesets and named checks | Prefer a protected `main` with stable checks over copying `develop`/`staging`; exact check names and review requirements need observed successful target runs and owner configuration. |

## Target repository evidence

- The target has a Python 3.11 package, FastAPI process/health routes, Docker Compose services, unit/integration tests, CI and security workflows, issue templates, a PR template, and Dependabot. It does not have an application Dockerfile, lockfile, full-stack query API, release pipeline, or measured production profile.
- The user-provided Actions screen showed the dependency-audit job failing because RAGAS pulled `diskcache` 5.6.3. RAGAS was not imported by application code and its evaluation harness has no published reproducible benchmark. It was removed from both runtime and optional dependencies. The local equivalent of the runtime dependency audit now reports **No known vulnerabilities found**.
- A strict local Zensical build reports **No issues found**. The local test suite reports **260 passed, 12 skipped** after three targeted regressions were added. The skipped MinIO tests still require a reachable service.
- GitHub Pages returned 404 and the REST branch-protection endpoint returned 404. No settings were changed; repository rulesets should be checked by an owner before claiming main is protected.

## Source links

- [ForgeStack repository](https://github.com/mangopep/forgestack)
- [ForgeStack Python CI](https://github.com/mangopep/forgestack/blob/main/.github/workflows/python-ci.yml)
- [ForgeStack CodeQL](https://github.com/mangopep/forgestack/blob/main/.github/workflows/codeql.yml)
- [ForgeStack secret scan](https://github.com/mangopep/forgestack/blob/main/.github/workflows/secret-scan.yml)
- [ForgeStack documentation checks](https://github.com/mangopep/forgestack/blob/main/.github/workflows/docs-check.yml)
- [ForgeStack release pipeline](https://github.com/mangopep/forgestack/blob/main/.github/workflows/release.yml)
