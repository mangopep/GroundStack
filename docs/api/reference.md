# API reference

The current FastAPI application implements only:

- `GET /`: returns a short process-running message.
- `GET /health`: returns `status: ok` and a descriptive message.
- `/workspace/`: serves the static early interface preview.

The health response uses `status: ok` and does not check dependencies. Query, ingestion, session, and feedback route modules are empty. No authentication is enforced. Run locally with `uvicorn src.api.main:app --reload --port 8000` after installing dependencies. OpenAPI docs are available at `/docs` while the process runs.
