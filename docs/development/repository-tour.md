# Repository tour

```text
src/api/          FastAPI process and (mostly empty) route/middleware modules
src/ingestion/    PDF parser, hierarchy chunker, index builder, directory watcher
src/workers/      in-memory async task queue and ingest worker
src/stores/       OpenSearch BM25, PostgreSQL structured KB, MinIO object adapter
src/llm/          Ollama wrapper and Redis cost tracker
src/schemas/      Pydantic knowledge contracts
scripts/          Compose initializers, corpus helpers, validation scripts
prompts/          prompt files (currently empty)
tests/            unit, integration, evaluation harness scaffolding
web/              static UI preview
```

For per-module status see [current state](../project/current-state.md). Many directories are intentionally listed even when their `.py` files are zero bytes; a filename alone does not imply functionality.
