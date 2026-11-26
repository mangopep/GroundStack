# API examples

Start the app in one terminal:

```bash
.venv/bin/python -m uvicorn src.api.main:app --reload --port 8000
```

In another terminal:

```bash
curl -i http://127.0.0.1:8000/
curl -i http://127.0.0.1:8000/health
curl -I http://127.0.0.1:8000/workspace/
```

Expected: HTTP 200 for each path. `/health` indicates process response only. These examples do not prove database or search readiness. No ingest/query example exists because those routes are not implemented.
