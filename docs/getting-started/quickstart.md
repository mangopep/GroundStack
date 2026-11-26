# Quickstart

There is not yet a verified one-command end-to-end demo. The existing API process can be started after installing the project dependencies:

```bash
.venv/bin/python -m uvicorn src.api.main:app --reload --port 8000
```

- `GET /` returns a process-running message.
- `GET /health` returns `status: ok`; it does not check backing services.
- `/workspace/` serves a static UI preview.
- `/docs` shows the FastAPI OpenAPI page; it currently documents only the basic routes.

No document upload or query endpoint is available. To understand the existing file-watcher path, read [first document](first-document.md). Do not treat the watcher as an HTTP API.
