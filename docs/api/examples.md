# API examples

The only implemented examples are process checks:

```bash
curl -s http://localhost:8000/
curl -s http://localhost:8000/health
```

`GET /` currently returns a JSON message. `GET /health` returns a JSON object with `status` and `message`. There are no implemented document-ingestion or query request/response payloads; examples for those would be fabricated.
