# Privacy status

The app is designed around local services, but local inference alone does not prove that all data stays local. Langfuse can receive traces/events when configured; Ollama host and external networking depend on operator settings. Current tracing has no centralized redaction guarantee.

Do not ingest private/sensitive documents into a publicly exposed environment. Before enabling telemetry, document fields, destination, retention, access, and deletion. Never publish real PDFs, prompts, dumps, `.env`, or model output in issues.
