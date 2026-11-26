# API authentication status

Authentication is not implemented. `src/api/middleware/auth.py` is zero bytes, and the `api_key` setting is not enforced. Do not expose the API or workspace to untrusted users/networks and do not rely on document isolation.

A production design must authenticate a principal, authorize collection/document scope on each operation, scope search inside datastore queries, rate-limit expensive parsing and model calls, and redact logs. A single shared API key would not provide tenant isolation or per-user auditability.
