# Implementation status

Statuses describe the security-foundation follow-up after `6df11e8`. Workflow-file presence alone is not remote verification; see [CI/CD evidence](../infrastructure/cicd.md).

| Capability | Status | Evidence / limitation |
|---|---|---|
| Basic FastAPI process | Implemented and smoke-tested | `/`, `/health`, `/workspace/`; health is not dependency readiness |
| PDF native text extraction | Implemented; partially verified | Docling primary parse, PyMuPDF fallback; status can be `partial_fallback` |
| OCR for scanned pages | Missing in current parser path | scanned pages without text are marked skipped |
| PDF tables/images as structured assets | Partial | page model fields exist, but parser emits empty lists; table heuristics use chunk text |
| Hierarchy-aware chunking | Implemented; unit-tested | deterministic chunk records; token count is heuristic |
| BM25 lexical retrieval | Implemented; unit and real service integration tested | Disposable OpenSearch adapter round trip passes |
| MinIO original-document storage | Implemented; unit and real service integration tested | Disposable MinIO tests pass and remove test buckets |
| PostgreSQL structured KB | Implemented; unit and real service integration tested | Disposable PostgreSQL tests pass; no migrations/versioned schema lifecycle |
| Filesystem watcher | Implemented; unit-tested | local thread pool; no durable jobs; separate from TaskQueue |
| Async task queue | Implemented in memory; unit/integration tests pass | restart loses state; reindex/summarize placeholder handlers |
| Document identity/versioning | Partial | `doc_id` is path hash; no content hash/version manifest |
| Embeddings and vector search | Missing | placeholder modules; no vectors in index path |
| Query orchestration/hybrid search | Missing | no query API; no RRF or hybrid ranker |
| Reranking/context assembly | Missing | zero-byte modules |
| Graph extraction/entity resolution | Missing | AGE enabled in Compose but no graph build flow |
| Generation/verification/citations | Missing as app flow | Ollama wrapper exists but no evidence-backed answer use case |
| Human corrections/audit history | Partial placeholder | schema/store placeholder but no user flow or conflict resolution |
| Authentication/authorization | Missing | middleware and route files empty |
| Deletion/reindex reconciliation | Partial | BM25 delete by document exists, but coordinated deletion is not wired |
| Backup/restore | Missing | backup shell script is empty; no restore drill |
| Observability | Partial | optional Langfuse calls in LLM/ingestion code, no request tracing or defined metrics path |
| Web interface | Preview only | static content, no upload or query integration |
| GitHub Pages docs | Build configured; publishing disabled | PR build and trusted-main deploy are conditional on owner configuring Pages, branch protection, and `PAGES_DEPLOYMENT_ENABLED=true` |
| Pull-request CI | Implemented; follow-up run pending | Exact lock install, pip-audit, Bandit, Ruff, strict scoped mypy, OpenAPI drift check, 75% coverage, Node syntax, strict docs build |
| Container verification | Implemented; local checks pass, remote run pending | Non-root API preview, AMD64/ARM64 OCI build, Trivy, Hadolint, SBOM, read-only/health/shutdown checks; no registry push |
| Clean development startup | Implemented as remote verification job | Starts PostgreSQL/AGE, OpenSearch, Redis, MinIO, and Langfuse with fake credentials on a fresh hosted runner; local running development services were preserved |
| Trusted release | Implemented as dry-run default; rehearsal pending | Tag/ancestry/check-run validation, scan exact OCI candidate, CycloneDX, GitHub provenance, Cosign verification, GHCR/GitHub Release behind variable and approved environment |
| GitHub governance | Owner configuration required | Public repository has no branch protection/rulesets; Pages disabled; no release approval environment; no settings were changed |
| 8 GiB hardware profile | Not tested | host reports 16 GiB RAM; current stack memory is high |
| Reproducible installs | Implemented | Universal hash-locked dev/ingestion and API runtime files; tested with Python 3.11.5+; `psycopg-pool`, `watchdog`, and Bandit are declared and locked |
