# Configuration internals

`src/config/settings.py` defines `Settings(BaseSettings)` and small per-service Pydantic models. `get_settings()` is an `lru_cache` singleton. A `.env` file is loaded by Pydantic Settings when the settings object is created; separately, `src/ingestion/pdf_intelligence.py` calls `python-dotenv.load_dotenv()` as an import side effect. Several adapters read `os.environ` directly, so Pydantic is not the only configuration path.

Connection values include PostgreSQL host/port/user/password/database, OpenSearch host/port/index, Redis host/port, MinIO endpoint/credentials/bucket, Ollama host/model, Langfuse host/keys, and log/reranker settings. The API key setting is not enforced by middleware.

For variable names and security limitations, use [configuration reference](../reference/configuration.md). Never add actual `.env` values to docs, command output, tests, or commits.
