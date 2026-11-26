# Configuration reference

Environment names below are read by `src/config/settings.py`, adapters, or Compose. Do not print values in support requests.

| Group | Variables | Use |
|---|---|---|
| PostgreSQL | `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | metadata and structured KB |
| OpenSearch | `OPENSEARCH_HOST`, `OPENSEARCH_PORT`, `OPENSEARCH_INDEX`, optional username/password in initializer | BM25 index; local Compose disables security |
| Redis | `REDIS_HOST`, `REDIS_PORT` | current cost tracker support; task queue is in-memory |
| MinIO | `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_BUCKET` | source object store |
| Ollama | `OLLAMA_HOST`, `OLLAMA_MODEL` | host generation wrapper; model default `llama3.2:1b` is not benchmarked |
| Langfuse | `LANGFUSE_HOST`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | optional tracing/events |
| App | `API_KEY`, `LOG_LEVEL`, `RERANKER_THRESHOLD` | API key is not enforced; reranker module is not implemented |
| Compose | `LANGFUSE_NEXTAUTH_SECRET`, `LANGFUSE_SALT`, plus DB/MinIO root variables | local services |

Use `.env.example` as a variable-name template only. The checked-in `.env` is ignored and must remain private.
