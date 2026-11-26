# CI/CD status

`.github/workflows/ci.yml` installs the hash-locked requirements, runs `pip-audit` against exact locked versions, checks Ruff lint/format, strictly type-checks the validated configuration and schema boundary modules, and runs pytest on pushes and PRs. It also runs on a weekly schedule so newly disclosed dependency advisories are checked. The same commands pass locally; GitHub Actions has not yet verified this updated workflow.

`.github/workflows/security.yml` runs CodeQL for Python and JavaScript/TypeScript plus full-history Gitleaks scanning. The third-party actions in the changed workflows are pinned to immutable SHAs, checkout does not persist credentials, and the default token scope is read-only except CodeQL's job-level `security-events: write`. Existing open Dependabot PRs still need separate review.

The docs workflow builds strict Zensical output on every pull request, avoiding path-filtered missing check statuses. On `main`, it uploads and deploys the Pages artifact only when `PAGES_DEPLOYMENT_ENABLED=true`. To publish safely, an owner must first protect `main`, set **Settings → Pages → Build and deployment → Source** to **GitHub Actions**, then add that repository Actions variable. These settings were not changed during recovery. The Pages API and branch-protection endpoint currently return 404, so publication from a verified protected branch is not yet enabled.

No release workflow, SBOM generation, container scanning, license compliance gate, provenance attestation, or database migration validation is configured. A release pipeline should add these only after their scope and supply-chain policy are clear.
