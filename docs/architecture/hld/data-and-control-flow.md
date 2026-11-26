# HLD: Data and control flow

## Ingestion control flow (current)

1. A filesystem event reaches `PDFEventHandler`.
2. `IngestionWatcher.enqueue_file()` checks suffix, stability, and debounce, then adds an `IngestionJob` to a Python heap.
3. A dispatch thread submits the job to a `ThreadPoolExecutor`.
4. `_run_ingestion()` calls `index_builder.ingest_pdf()` directly.
5. The builder parses, chunks, writes OpenSearch and selected structured KB records, uploads the PDF, upserts metadata, and returns a result.

The separate async TaskQueue has its own worker loop and default handlers. It is not the watcher’s queue and does not persist to Redis.

## Query control flow (current)

There is no HTTP query control flow. The lexical adapter and LLM client exist independently; no application module coordinates them.

## Cross-store consistency

The current writes are sequential but not one transaction. A failure can leave some stores changed and others unchanged. Recovery currently relies on reruns/operations rather than a persisted manifest and reconciliation job. This is a release blocker for reliable document lifecycle management.
