# LLD: Ingestion modules

## Input and output contracts

- Entry point: `src/ingestion/watcher.py:IngestionWatcher._run_ingestion(path, priority_label)` calls `src/ingestion/index_builder.py:ingest_pdf(path)`.
- Parser: `process_pdf(path) -> list[PageResult]`; `PageResult` contains 1-based page number, text, `native|scanned`, and `success|partial_fallback|failed|skipped` status.
- Chunker: `chunk_pages(page_results, doc_id) -> list[ChunkResult]`; chunk records contain deterministic ID, `doc_id`, section title/path, content, page numbers, type, parent and structural metadata.
- Builder: `ingest_pdf(path) -> IngestResult`; reports document ID, filename, page/chunk/table/indexed counts, MinIO key, status, and warnings.

## Algorithms and complexity

- Page classification reads each page's extracted text. For `P` pages and `B` source bytes, parser cost is dominated by PDF decoding/OCR model work and document structure; no stable upper bound is measured.
- Repeated-line detection in `chunk_pages` scans line text into per-line page sets. Expected work is linear in input characters/lines plus page ordering; memory grows with lines, mappings, and emitted chunks.
- Paragraph splitting estimates tokens by character heuristics. It targets a configured max and best-effort minimum; it does not call a tokenizer.
- Chunk identifiers are deterministic SHA-256-derived values based on document/type/content/scope helpers. Document identity itself is a hash of the absolute path, not file content.
- The builder loops over chunks and issues OpenSearch/SQL writes sequentially. Runtime grows with parsing plus all external calls; it is not a bulk/transactional multi-store commit.

## Failure handling

Parser errors can fail the whole operation. Per-chunk indexing and structured extraction errors are collected as warnings and status becomes `partial`; PDF upload or metadata errors propagate after earlier writes may already have succeeded. There is no rollback or reconciliation record. The watcher logs job failure but has no durable status endpoint.

## Safe extension points

Keep source page/version metadata on `ChunkResult`; add parser behavior behind `PageResult`; add an explicit manifest and idempotent version policy before changing IDs or deletion. Test native PDF, scanned image-only PDF, multi-page tables, command fidelity, duplicate re-ingestion, and partial-store failures.
