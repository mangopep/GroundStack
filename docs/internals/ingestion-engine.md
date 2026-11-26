# Ingestion engine: source walkthrough

## The problem it solves

PDFs are large, irregular files. Search needs smaller text records with useful section and page metadata. The current pipeline converts a path into page records, chunks, and writes to multiple stores.

## Entry point and call trace

The filesystem watcher dispatches to `IngestionWatcher._run_ingestion()` in `src/ingestion/watcher.py`, which calls `ingest_pdf()` in `src/ingestion/index_builder.py`:

1. Validate path exists and suffix is `.pdf`.
2. `compute_doc_id()` hashes the resolved path and truncates SHA-256 to 16 hex characters.
3. `process_pdf()` returns `PageResult` records.
4. `chunk_pages()` returns deterministic `ChunkResult` records.
5. Construct `BM25Store`, `DocStore`, and `StructuredKBStore`.
6. For each content-bearing chunk, index to OpenSearch. For table chunks, apply heuristics and insert a small subset of `KnowledgeObject` types.
7. Upload original PDF to MinIO.
8. Upsert `document_metadata` in PostgreSQL.
9. Emit optional Langfuse event and return `IngestResult`.

## Input and output

Input is a local file path. Output contains `doc_id`, counts, MinIO key, `success|partial`, and warnings. This is a Python function, not an HTTP endpoint.

## What can go wrong

- Scanned page without usable text is skipped: OCR is not implemented in this path.
- Docling can return empty page text; PyMuPDF fallback keeps text and labels it `partial_fallback`.
- Per-chunk OpenSearch and table-store errors can leave a partial ingestion; later object or metadata failure can occur after earlier writes.
- Path-derived document IDs do not track file content versions.
- Stores are not committed atomically; retries can encounter leftovers.

## Complexity and resources

Parsing and OCR/model inference dominate. Chunk processing is approximately linear in extracted characters plus repeated-line maps and emitted records. Writes currently issue one OpenSearch operation per chunk, so external round trips scale with chunk count. No throughput or peak-memory benchmark is published.

## Debugging and tests

Use the [PDF parser guide](document-parsing.md), [chunking guide](chunking-engine.md), unit tests under `tests/unit/test_chunker.py` and `test_index_builder.py`, and service-backed tests only when the backing services are available. Current full-stack ingestion was not run in the baseline. Do not retry a partial ingestion blindly until idempotency and cross-store reconciliation are implemented.
