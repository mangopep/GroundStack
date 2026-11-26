# LLD: Queue and watcher

## Watcher implementation

`IngestionWatcher` uses Watchdog for non-recursive filesystem events, an in-memory `heapq` ordered by priority/counter, a dispatch thread, and a `ThreadPoolExecutor`. Events are accepted after a file-size stability check and per-path debounce. The executor directly calls `ingest_pdf()`.

For queue depth `Q`, heap insertion/removal is O(log Q); memory is O(Q) plus active futures. Parallel work is bounded by `max_workers` in one process. A process restart loses pending jobs. A duplicate event after restart can re-ingest the same path.

## Async TaskQueue implementation

`TaskQueue` keeps a Python `asyncio.PriorityQueue`, task registry, status counts, and worker tasks in memory. Enqueue/dequeue operations are O(log Q) for the priority queue; active concurrency is bounded by configured workers. It is independent of Redis and independent of the watcher.

`IngestWorker` wraps a queue handler with retry/status/file-management code but is not started from FastAPI. Queue ingest import errors now propagate. Reindexing and summarization still simulate work and must be replaced before the queue is used as a production job system.
