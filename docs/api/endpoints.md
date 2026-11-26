# Endpoint reference

## `GET /`

Returns a JSON object containing a process-running message.

## `GET /health`

Returns JSON with `status: "ok"` and a message that dependency readiness is not checked. Do not use this as an orchestrator readiness probe.

## `/workspace/`

Static responsive interface preview. It does not upload documents or query indexes.

There are no current document, query, feedback, session, or delete endpoints. The similarly named modules under `src/api/routes/` are empty. No request/response schema should be invented for them.
