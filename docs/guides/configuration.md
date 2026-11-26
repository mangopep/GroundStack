# Configuration

`src/config/settings.py` uses Pydantic Settings and reads `.env`. Current configuration includes PostgreSQL, OpenSearch, Redis, MinIO, Ollama, Langfuse, and application values.

| Variable group | Purpose | Notes |
|---|---|---|
| `POSTGRES_*` | database connection | never use sample credentials outside an isolated local environment |
| `OPENSEARCH_*` | lexical index endpoint/name | current Compose disables security |
| `REDIS_*` | Redis endpoint | queue/cache durability is not proven |
| `MINIO_*` | S3-compatible endpoint and credentials | rotate defaults immediately |
| `OLLAMA_*` | local model server/model | model availability depends on host and RAM |
| `LANGFUSE_*` | optional tracing | enabling sends telemetry to configured endpoint |
| `API_KEY` | legacy application setting | not currently enforced by API middleware |

Settings defaults in the current source include development secrets. This is a known issue; do not expose the service. See the security roadmap.
