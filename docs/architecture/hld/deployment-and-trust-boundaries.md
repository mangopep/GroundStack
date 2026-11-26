# HLD: Deployment and trust boundaries

## Current topology

Docker Compose provides PostgreSQL/AGE, OpenSearch, Redis, MinIO, Langfuse, and an optional API preview under the `api` profile. The image contains only current process-health and static-workspace routes; it does not implement ingestion/query handlers. Compose service ports bind to loopback. OpenSearch security is disabled, and the API has no auth middleware, so this remains a development topology.

The static docs site will be built into a Pages artifact by GitHub Actions. GitHub Pages is currently disabled (the Pages API returned 404), so the workflow can be prepared locally but a GitHub setting change is still required before publishing.

## Target trust boundaries

Documents, extracted text, model outputs, and browser-provided metadata are untrusted. Authentication must establish principal and tenant scope before ingestion/query. Store queries must enforce that scope; filtering results only after retrieval is not sufficient. Model output should be treated as untrusted until validated against retrieved evidence.

No such enforcement currently exists. Do not expose the current topology on an untrusted network.
