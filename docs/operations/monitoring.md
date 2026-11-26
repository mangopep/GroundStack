# Monitoring

The repository contains empty metrics/tracing modules. Langfuse is optionally called by the LLM wrapper and ingestion event code, but request/task correlation, redaction, and telemetry coverage are not established. Docker health checks only indicate selected process-level responses.

A useful operational baseline should record queue age, parse outcome counts, per-store write failures, index/search latency, job retries, RSS/container memory, disk, and error correlation IDs. Avoid document text and credentials in labels/logs. No production alerts or SLOs exist.
