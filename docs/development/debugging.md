# Debugging

- Start with the exact test or script and inspect its store adapter call.
- For API issues, distinguish liveness (`/health`) from service connectivity.
- For PDF issues, inspect per-page extraction status before changing chunking.
- For indexing, compare `ChunkResult` fields, OpenSearch mapping, and `_source` records.
- For PostgreSQL, verify schema version and connection string without printing credentials.
- For worker issues, identify whether the caller is the Watchdog thread pool or the separate asyncio queue.

Use sanitized logs, avoid printing local `.env`, source PDF text, model prompts, or response payloads. The current code lacks correlation IDs; include task/document identifiers only if they are not sensitive.
