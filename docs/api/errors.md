# API errors

The basic root and health routes do not define a shared error schema. FastAPI's default validation/error responses apply to framework errors, but there are no application error codes, correlation IDs, retry guidance, or stable endpoint contract yet.

Before adding endpoints, define errors for malformed input, unsupported file type/size, missing document, unauthorized scope, dependency unavailable, job failure, and evidence-insufficient answer. Do not return raw exception text or private document content to clients.
