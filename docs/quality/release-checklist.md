# Release readiness gates

A release is blocked until applicable gates have evidence:

- [ ] Clean install from a pinned dependency lock on supported Python/OS/ARM64 combinations.
- [ ] CI lint, formatting, unit, contract, integration, and e2e jobs pass.
- [ ] No false-success placeholders or destructive normal startup operations; remaining placeholders are replaced or clearly excluded from release scope.
- [ ] Ingest, query, deletion, restart recovery, and backup/restore pass with real services.
- [ ] Auth, authorization, tenant isolation, rate limits, and prompt-injection controls are tested before multi-user use.
- [ ] Quality/latency/memory results include corpus and hardware details; no fabricated metrics.
- [ ] Dependency/container/secret scans, license review, SBOM, and artifact provenance are reviewed.
- [ ] Docs strict build, link checks, API reference, and examples pass.
- [ ] Changelog, semantic version, rollback notes, support/security process, and known limitations are published.

Current release readiness: **NOT READY**. No stable release exists.
