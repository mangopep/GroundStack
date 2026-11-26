# Troubleshooting

- **Dependency install is large or slow:** the `ingestion` extra includes Docling/OCR and related transitive packages. The API container uses only the small FastAPI/Uvicorn runtime lock.
- **Compose fails to start:** inspect `docker compose ps` and `docker compose logs <service>`. OpenSearch can be memory intensive.
- **API health returns `ok`:** this currently means the process responds; it is not a dependency readiness check.
- **Tests cannot connect:** integration tests require the corresponding PostgreSQL, OpenSearch, or MinIO service and fixture configuration.
- **No `pytest` command:** activate the project environment and install `.[dev,ingestion]` or run `make setup`.

Provide sanitized logs and commit ID when reporting issues. Do not include secrets or private document contents.
