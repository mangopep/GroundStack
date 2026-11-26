# Security and privacy

## Known current risks

- Compose now requires database, MinIO, and Langfuse secrets from an ignored `.env` file, but OpenSearch security remains disabled for local development.
- The API has no authentication, authorization, tenant filtering, or rate limiting.
- The deployment is a development topology and must not be exposed to public networks.
- No prompt-injection, cross-tenant, or document-deletion security suite has been run.
- Local inference does not by itself guarantee that all telemetry or other configured integrations stay local.

## Required before production

Use secrets outside source control; enable TLS and backend authentication; enforce authorization at every API and datastore boundary; isolate tenant indexes/collections or apply tested mandatory filters; validate upload size/type and parser resource limits; limit network egress; redact logs; scan dependencies/images and secrets; rotate credentials; and test restore and deletion. These are recommendations, not existing guarantees.
