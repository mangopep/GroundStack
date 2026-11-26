# ADR 0004: Promote the scanned OCI archive for releases

- Status: Accepted for the current API preview; production rollout remains gated on repository settings and a successful rehearsal.
- Date: 2026-11-26

## Context

GroundStack needs repeatable releases with evidence tied to the shipped image digest. Rebuilding after a scan can produce a different artifact, even when the source revision is unchanged. Normal pull-request workflows must not publish packages, and maintainers have not yet configured branch protection or release-environment approval.

## Decision

The manually dispatched release workflow defaults to a non-publishing rehearsal. It builds one multi-platform OCI archive, scans that archive, generates its SBOM, and retains the archive as a workflow artifact. Publishing is conditional on explicit dispatch input, a matching semantic-version tag descended from `main`, successful quality/security check runs on that commit, an unused release identity, a repository enablement variable, and approval in the `release` environment. The publish job copies the already-scanned archive to GHCR, signs and attests its immutable digest, verifies those records, then creates the GitHub Release and digest manifest.

## Consequences

- The candidate that was scanned is the candidate that is published.
- Fork and pull-request workflows have no write permissions or publication credentials.
- Maintainers must configure protected `main`, the release environment reviewers, and enablement variable before the workflow can publish.
- The current API preview is the only deployable GroundStack image. Database migrations, release deployment, and data rollback remain separate work.
- Rehearsal artifacts expire after 30 days; published SBOM, provenance, signature, and manifest remain associated with the release/image digest.
