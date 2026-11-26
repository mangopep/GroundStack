# Implementation status

Statuses describe code and tests at commit `c452050`. A green unit test does not mean the real service integration is verified.

| Capability | Status | Evidence / limitation |
|---|---|---|
| Basic FastAPI process | Implemented and smoke-tested | `/`, `/health`, `/workspace/`; health is not dependency readiness |
| PDF native text extraction | Implemented; partially verified | Docling primary parse, PyMuPDF fallback; status can be `partial_fallback` |
| OCR for scanned pages | Missing in current parser path | scanned pages without text are marked skipped |
| PDF tables/images as structured assets | Partial | page model fields exist, but parser emits empty lists; table heuristics use chunk text |
| Hierarchy-aware chunking | Implemented; unit-tested | deterministic chunk records; token count is heuristic |
| BM25 lexical retrieval | Implemented; unit-tested | OpenSearch adapter; integration path not included in passing baseline test evidence |
| MinIO original-document storage | Implemented; unit-tested with mocks | MinIO service integration suite skipped in baseline |
| PostgreSQL structured KB | Implemented; unit and local service tests pass | no migrations/versioned schema lifecycle |
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
| GitHub Pages docs | Not deployed | no Pages configuration; Pages API returns 404 |
| 8 GiB hardware profile | Not tested | host reports 16 GiB RAM; current stack memory is high |
| Reproducible installs | Missing | no lockfile; broad unbounded runtime dependencies |
