# Observability

Langfuse, tracing, and metrics dependencies/modules are present, but end-to-end instrumentation and privacy policy are not verified. Before enabling telemetry, document data sent, endpoint, retention, and redaction. Target signals include request/job correlation IDs, queue age, parse failures, index-write failures, retrieval latency, token usage, citation coverage, and store health. Avoid logging document text or secrets by default.
