# Docker Compose

`docker-compose.yml` defines PostgreSQL/AGE, OpenSearch, Redis, MinIO, and Langfuse with named volumes. The Python app and Ollama run on the host. PostgreSQL, OpenSearch, Redis, MinIO, and Langfuse ports are published to the host. OpenSearch security is disabled, so this is a local development topology, not a network boundary.

## Inspect before start

From the repository root, ensure `.env` exists and contains the variables required by Compose. Preserve any existing secrets file.

```bash
# Safe read-only validation; does not start or modify containers
 docker compose config --quiet
# Read current service state
 docker compose ps
```

Then, only for a deliberate local development start:

```bash
# Starts services and may create persistent named volumes
 docker compose up -d
```

`docker compose down` stops/removes containers but retains named volumes. **`docker compose down -v` deletes all named volumes**, including local PostgreSQL, OpenSearch, MinIO, and Redis data. It is destructive and not a routine troubleshooting command.

## OpenSearch initialization warning

At the audit baseline, `scripts/startup.sh` called `scripts/init_opensearch.py`, whose `create_index()` deleted an existing index before recreating it. The recovery change makes initialization create-only and preserves existing index contents. It does not migrate mappings. The index still uses two shards/one replica despite a single-node local service, and OpenSearch's memory limit is 1 GiB. Audit snapshot usage was about 1 GiB.

## Image and health concerns

`minio/minio:latest` is mutable. Pin a tested image version and record supported architectures before release. Compose health checks exist for services, but app readiness/start ordering is not established. A healthy container does not prove ingestion/query correctness.
