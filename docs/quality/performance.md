# Performance status

No throughput or latency claim is supported. Parsing is likely dominated by Docling model/CPU work; the current builder performs per-chunk OpenSearch requests and sequential storage operations. The queue/watcher concurrency is process-local and configured as workers, but resource consumption has not been bounded against an 8 GiB host.

Before optimizing, profile a licensed representative corpus and separate parser, chunker, embedding (future), indexing, search, and generation timings. Avoid increasing concurrency while OpenSearch is near its memory cap.
