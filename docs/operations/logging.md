# Logging

Some ingestion, store, watcher, and queue modules use Python logging; `src/utils/logger.py` is empty. There is no shared JSON logging setup, request ID middleware, or proven redaction policy. Avoid passing raw document content, prompts, credentials, or model responses to logs. When investigating, sanitize and retain only task/document identifiers that are approved for operational use.
