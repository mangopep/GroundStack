# Roadmap

The root [ROADMAP.md](https://github.com/mangopep/rag_platform/blob/main/ROADMAP.md) remains the single editable roadmap. The dependency order is:

1. Add explicit OpenSearch mapping migrations; establish repeatable ingest identity and cross-store recovery semantics.
2. Resolve dependency/lock/configuration baseline and make CI green.
3. Define document manifest, idempotency, versioning, deletion, and recovery semantics.
4. Build one real, service-backed ingestion vertical slice from API request to persisted document state.
5. Add a retrieval/answer vertical slice only after the manifest and retrieval contracts are stable.
6. Add authentication and scope enforcement before exposing any multi-user API.
7. Measure quality and resource consumption on a redistributable corpus, including the actual 8 GiB target.
8. Add verified backup/restore and production deployment guidance after recovery behavior is proven.

Do not interpret a roadmap item as implemented. See [implementation status](implementation-status.md).
