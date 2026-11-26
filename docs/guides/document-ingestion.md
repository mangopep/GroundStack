# Document ingestion

The repository includes watcher/worker and parser/index-builder modules. Their service-backed path is not exposed through a working HTTP endpoint and was not verified during this audit. Review `src/ingestion/` and `src/workers/` before use. Start with synthetic or public test documents; do not assume duplicate, resume, delete, or page citation behavior is complete.
