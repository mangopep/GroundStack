# Development history

This is a reconstruction from Git commits and repository contents, not a claim about undocumented intent.

## 2026-03-07 — Initial foundation

Commit `624c7b9` introduced the initial repository layout, a Compose stack, centralized settings, an Ollama/Langfuse wrapper, database and OpenSearch initialization scripts, ingestion utilities, and initial phase documentation. The commit body says a real RFC corpus of 318 pages was tested. Most files in `src/ingestion`, `src/stores`, `src/api/routes`, and several other areas were zero bytes in this commit, so the current implementation was added later.

## 2026-03-07 — Phase 1 documentation edit

Commit `e7ce30a` changed `docs/Phase1.md`; its subject is only `phase1.md`.

## 2026-03-10 — Ingestion implementation

Commit `6b87f55` added PDF intelligence, an 802-line hierarchy-aware chunker, a 635-line index builder, BM25/PostgreSQL/MinIO stores, an in-memory async task queue, a worker, a directory watcher, and unit/integration tests. Its commit body records earlier validation metrics and a breaking cleanup of legacy chunks. These are statements in the commit message, not independently re-run results in this recovery audit.

## 2026-11-26 — GroundStack foundation

Commit `c452050` introduced the GroundStack name, project policies and architecture status documents, a static web preview, secret-required local Compose configuration, basic CI/security workflows, and an Ollama 1B default. It did not implement the missing query or authorization paths.

## Repository state at recovery

The local repository has `main` only, no tags, and no GitHub Releases. The remote exposes `main` and four Dependabot branches. GitHub lists four open dependency PRs: Langfuse, Gitleaks Action, checkout, and setup-python. No PR was merged or modified during the audit.
