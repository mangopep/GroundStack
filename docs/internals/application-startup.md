# Application startup

## Current startup

`src/api/main.py` constructs a FastAPI app at import time and mounts `/workspace/` from the repository's `web/` directory. Uvicorn imports `src.api.main:app`. There is no lifespan function that creates stores, starts workers, or checks dependencies.

The shell startup script checks Docker, Ollama, and Python, launches Ollama if it cannot find a process, pulls the configured local model, runs `docker compose up -d`, waits for selected services, then invokes OpenSearch and MinIO initialization. It reports readiness even when some initialization steps only warn. The OpenSearch initializer is now create-only; schema changes still need migrations. See [Docker operations](../infrastructure/docker.md).

## What happens without initialization?

The API can still respond, but its health response means only “the process is responding.” Indexing/storage operations fail when the corresponding external service or schema is unavailable.

## Debugging and testing

Start the API directly for a process smoke test; use Docker/adapter integration tests for stores. Do not call the health endpoint a readiness check. A future lifespan manager should expose separate liveness and readiness and shut down the worker with a bounded drain.
