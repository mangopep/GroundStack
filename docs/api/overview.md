# API overview

The FastAPI application is `src.api.main:app`.

| Route | Current behavior |
|---|---|
| `GET /` | Returns a JSON process-running message |
| `GET /health` | Returns `status: ok`; checks only that the handler responds |
| `/workspace/` | Serves the static UI preview |
| `/docs` | FastAPI's generated OpenAPI UI for the two API endpoints |

The route files for ingest, query, feedback, and sessions are empty and are not registered. No authentication or rate limiting is enforced. See the [reference](reference.md) and [working examples](examples.md).
