# LLD: Current persistence adapters

| Adapter | Source and actual API | Current owner/limit |
|---|---|---|
| OpenSearch | `src/stores/bm25.py:BM25Store.index_chunk`, `search`, `delete_by_doc_id` | lexical chunks; page field mapping differs from initializer; not canonical document lifecycle |
| PostgreSQL | `src/stores/structured_kb.py:StructuredKBStore` plus `scripts/init_db.sql` | JSONB structured KB, metadata and feedback/override tables in SQL; no migration framework |
| MinIO | `src/stores/doc_store.py:DocStore` | source PDF/image object operations; real service test skipped in baseline |
| Redis | `src/llm/cost_tracker.py:CostTracker` | model-use accounting; not the task queue or retrieval cache |
| AGE | image and graph init SQL only | no Python graph adapter or graph lifecycle |
| pgvector | no extension enabled | not implemented |

No single storage system owns an atomic, versioned document manifest. `ingest_pdf()` makes sequential writes, so consistency after process/service failure is not guaranteed.
