# Code-reading guide

Read one concrete flow instead of inferring behavior from the directory names:

1. Start at `src/ingestion/watcher.py:PDFEventHandler.on_created()`.
2. Follow `IngestionWatcher.enqueue_file()` → `_dispatch_loop()` → `_run_ingestion()`.
3. Follow `src/ingestion/index_builder.py:ingest_pdf()`.
4. Follow `process_pdf()` and `chunk_pages()`.
5. Inspect the adapter calls in `src/stores/bm25.py`, `structured_kb.py`, and `doc_store.py`.
6. Compare with `tests/unit/test_index_builder.py` and service-backed integration tests.

Then read the [query LLD](../architecture/lld/query.md): it makes clear that no active query endpoint joins BM25 to the LLM client.
