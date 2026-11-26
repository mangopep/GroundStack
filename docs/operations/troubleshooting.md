# Troubleshooting

- **Compose config says a secret is missing:** inspect only variable names, not secret values. Preserve any existing `.env`; create it from `.env.example` only when absent.
- **`/health` is `ok` but ingestion fails:** it is a liveness endpoint; check service reachability and adapter logs independently.
- **OpenSearch is near 1 GiB:** current Compose limit is 1 GiB and audit stats were near the cap; reduce test corpus/concurrency or increase a deliberate local Docker allocation after measuring.
- **PDF pages are `partial_fallback`:** Docling returned no page text and PyMuPDF was used. This is not OCR, and command/table fidelity still needs fixture checks.
- **No query endpoint:** this is a missing feature, not a client configuration issue.
- **MinIO tests skip:** the integration guard checks actual credentials/endpoint reachability; run only after configuring the test service.

Do not use `docker compose down -v` or run the current startup script against valuable indexes to fix connectivity.
