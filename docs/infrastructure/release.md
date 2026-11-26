# Trusted release process

## What a release contains

The release target is the current FastAPI process-health and static-workspace preview only. It is not a full ingestion worker or RAG query service. The candidate is a multi-architecture OCI archive for `linux/amd64` and `linux/arm64`, built from one source revision with a semantic-version OCI label. Before publication the workflow scans that exact archive, creates a CycloneDX SBOM, and stores the candidate as a 30-day workflow artifact.

## Rehearse without publishing

1. Open **Actions → Trusted release → Run workflow** on `main`.
2. Enter a candidate semantic version such as `0.1.0-rc.1` and leave **publish** unchecked.
3. Wait for `verify`, `quality`, and `candidate`. Quality includes hash-locked dependency checks, Bandit, Ruff, scoped strict mypy, API OpenAPI drift validation, unit tests and coverage, strict docs and Mermaid validation, Compose validation, and the disposable four-service integration suite. Candidate builds and scans both OCI platforms without registry access.
4. Download the `groundstack-release-candidate-*` artifact and inspect its manifest and SBOM. The `candidate` manifest is explicitly marked `not-published`.

The workflow must complete this full rehearsal successfully before repository publishing controls are enabled. No real release has been made by this change.

## Publish a reviewed version

Publishing is gated by all of the following:

- Dispatch this workflow on a matching `vX.Y.Z` tag. The tag commit must be an ancestor of `main`.
- The same commit must have successful `python`, `build`, `codeql`, `secret-scan`, `services`, and `api-image` Actions checks.
- The tag and GitHub Release must be unused.
- Set repository Actions variable `RELEASE_PUBLISH_ENABLED=true` only after an owner has configured the `release` environment with required reviewers.
- Select **publish** in the manual dispatch and approve the environment deployment.

The publish job downloads and pushes the exact scanned OCI archive to GHCR under the version and source-SHA tags. If a version includes optional SemVer build metadata, `+` is mapped to `_` in the Docker tag because OCI tag syntax does not allow `+`; the immutable image digest is recorded in the release manifest. It then records the registry digest, produces GitHub build provenance, signs the image digest and SBOM attestations using keyless Sigstore, verifies them, and creates a GitHub Release containing a digest-addressed manifest and CycloneDX SBOMs. It never publishes a mutable `latest` tag.

If any gate fails, do not set the variable or approve the environment. Fix the source and repeat the dry run. The public repository currently has no protected branch rules and no configured `release` environment; publishing therefore remains unavailable until an owner configures those settings.

## Promotion and rollback

Consumers should deploy the immutable `ghcr.io/mangopep/groundstack/api@sha256:…` reference from the release manifest. Promote that same digest between environments; do not rebuild for staging or production. Verify the GitHub attestation and Sigstore signature before deployment. The application currently has no database migration release lifecycle or production deployment automation, so this workflow does not run `docker compose up` against a production environment.

To roll back, redeploy the previous known-good digest from its GitHub Release manifest and verify the API process and service health. Keep the failed release and its evidence for investigation; do not overwrite an existing version tag. Data rollback and cross-store recovery are not automated and must be planned separately before exposing ingestion to users.

## Trust boundary

Pull requests, including fork contributions, receive read-only repository permissions and do not receive release or registry credentials. The publish job runs only after quality and candidate jobs succeed, and only after a manual request on the matching tag plus an approved protected environment. Checkout persistence is disabled. Workflow actions and scanner images are pinned by immutable commit or digest references.
