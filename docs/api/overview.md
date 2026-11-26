# API overview

The committed [OpenAPI document](openapi.json) is generated from the FastAPI app with `python scripts/export_openapi.py`. CI checks for drift using `python scripts/export_openapi.py --check`. It describes only the current root and process-health endpoints; the static workspace mount is not an API operation.

The FastAPI application is `src.api.main:app`.

| Route | Current behavior |
|---|---|
| `GET /` | Returns a JSON process-running message |
| `GET /health` | Returns `status: ok`; checks only that the handler responds |
| `/workspace/` | Serves the static UI preview |
| `/docs` | FastAPI's generated OpenAPI UI for the two API endpoints |

The route files for ingest, query, feedback, and sessions are empty and are not registered. No authentication or rate limiting is enforced. See the [reference](reference.md) and [working examples](examples.md).
