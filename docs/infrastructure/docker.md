# Docker Compose

`docker-compose.yml` defines PostgreSQL/AGE, OpenSearch, Redis, MinIO, and Langfuse with named volumes. The Python app and Ollama run on the host unless the separately built API image is run directly. Third-party service images are pinned by manifest digest. Published ports bind to loopback only. OpenSearch security is disabled, so this is a local development topology, not a network boundary. The OpenSearch image also requires `OPENSEARCH_INITIAL_ADMIN_PASSWORD` for its demo bootstrap even while security is disabled; set a unique strong value in `.env`.

Compose creates a separate `langfuse` database, including when an existing PostgreSQL volume is reused, so Langfuse migrations stay isolated from the `rag_platform` application tables and AGE graph.

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

## API image scope

`Dockerfile` builds the currently implemented FastAPI process and static workspace preview. It does not include the optional document-ingestion dependencies or make the currently empty query/ingest routes functional. The image uses a small hash-locked API dependency set, a pinned multi-architecture Python base, an unprivileged numeric UID, an HTTP process health check, and no writable application directories. This is not a full RAG production deployment.

Build and run the API image without starting or changing the named service volumes:

```bash
docker build --tag groundstack-api:local .
docker run --rm --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --cap-drop ALL --security-opt no-new-privileges \
  --publish 127.0.0.1:8000:8000 groundstack-api:local
```

The API image exposes process liveness and the static preview only. It does not check database, search, queue, model, or object-store readiness.

## Image and health concerns

Compose health checks exist for services, but app readiness/start ordering is not established. A healthy container does not prove ingestion/query correctness. `docker-compose.integration.yml` uses a separate project, loopback-only ports, digest-pinned service images, and throwaway volumes for service tests; CI tears that project down after every run.
