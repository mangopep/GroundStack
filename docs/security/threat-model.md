# Threat model

## Assets

Source PDFs, extracted text/chunks, structured knowledge, embeddings/graph data if added, credentials, model prompts/responses, feedback, and user identity/scope.

## Current trust boundaries and threats

- Untrusted PDF contents can exploit parser resource limits or contain prompt injection.
- Host-published Compose ports and disabled OpenSearch security permit broad local access.
- API has no authentication or authorization; all current routes are unauthenticated.
- No tenant/document filters exist.
- Optional Ollama/Langfuse integrations may send prompt/evidence data to configured endpoints; no complete data-flow/redaction guarantee exists.
- Logs can include filenames, IDs, exception messages, or model traces; redaction is not centrally enforced.
- Baseline issue fixed in this recovery change: startup previously deleted the OpenSearch index; initialization now preserves existing index data.

## Required controls before production

Threat-model parser sandboxing and file-size/time limits; authenticate and authorize every request; enforce scoped queries in each store; handle prompt-injection text as data; use secrets/TLS/service ACLs; restrict egress; define telemetry retention/redaction; and test tenant isolation, deletion, and restore. These are requirements, not controls already implemented.
