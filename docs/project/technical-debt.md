# Technical debt register

Prioritized by risk and dependency, based on the 2026-11-26 audit.

## P0 — Data integrity and truthful status

1. **OpenSearch schema evolution has no migration path.** The baseline startup initializer deleted the index; this recovery change makes it create-only and preserves existing data. Add explicit, versioned schema migrations before changing mappings.
2. **Queue durability and placeholder handlers.** Ingest import errors now propagate and are covered by regression tests. The in-memory queue still loses state on restart, and reindex/summarize handlers still simulate work.
3. **Cross-store partial commits.** `ingest_pdf()` writes OpenSearch/structured rows before MinIO and metadata. A later failure can leave orphaned records. Define a manifest and reconciliation strategy before expanding ingestion API.
4. **Identity/version ambiguity.** Document identity is an absolute-path hash; content changes at a path reuse IDs, while moved files change IDs. Define content-addressed identity plus explicit versions and tenant/collection scope.
5. **No coordinated deletion.** Search delete exists, but document, SQL, object, and graph cleanup is not orchestrated.

## P1 — Architecture and security

6. API query/ingestion routes, auth middleware, embeddings, vector store, retrieval/answer/verification, and graph modules are empty.
7. Queue and watcher are separate and in-memory; task statuses are not durable, and no app lifecycle composes them.
8. No tenant/document authorization; OpenSearch security disabled; services bound on host ports.
9. PostgreSQL schema is a one-time init SQL script; no migration tool or compatibility policy.
10. Search mapping drift: initializer declares `page_number`, while `BM25Store` stores/expects `page_numbers`.
11. OpenSearch initialization uses two shards, one replica for a single-node local service; replicas will remain unassigned and consume unnecessary capacity.
12. `minio/minio:latest` is mutable; versions and ARM64 support are not recorded/tested as a complete matrix.

## P2 — Maintainability and operations

13. **Strict type checking is not configured.** Ruff and formatting pass locally after the recovery cleanup, but CI has no verified strict mypy/pyright check. Add it after selecting a bounded module scope and resolving real findings.
14. No application dependency lock. `docling`, `surya-ocr`, and many dependencies are unbounded. RAGAS was removed from project dependencies because its current graph includes [`diskcache` 5.6.3](https://osv.dev/vulnerability/PYSEC-2026-2447), which uses unsafe pickle deserialization and has no fixed version listed in the advisory. Add an evaluation package only after selecting a safe replacement or mitigation. Direct imports for `watchdog` and `python-dotenv` are not direct project dependencies.
15. Many empty legacy placeholders and empty scripts/docs remain tracked; duplicate old docs coexist with newer docs.
16. `init_db.sql` calls AGE graph creation in the init script but there is no graph schema lifecycle or migration.
17. Tests do not exercise all real services concurrently or persistence across restart. MinIO integration tests skipped in baseline.
18. Operational scripts have inconsistent configuration sources. Some use Pydantic settings, others read environment directly. `.env` is loaded as a side effect by the PDF parser.
19. No measured retrieval quality, citation accuracy, ingestion throughput, p95 query latency, or peak memory. Current report does not provide production readiness.
