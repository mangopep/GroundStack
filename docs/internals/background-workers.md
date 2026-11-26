# Background workers

There are two current mechanisms:

- `IngestionWatcher`: Watchdog events → in-memory heap → dispatch thread → thread pool → direct `ingest_pdf()` call.
- `TaskQueue` and `IngestWorker`: asyncio priority queue/task registry → async worker loops → registered handlers, with separate retry/status/file-management code.

Neither is persisted in Redis or PostgreSQL, and the API does not start them. A restart loses queued task state. Reindex and summarization queue handlers remain placeholders. The ingest handler now propagates import errors rather than simulating success; see the [technical debt register](../project/technical-debt.md). Do not run both mechanisms on the same directory without duplicate-work analysis.
