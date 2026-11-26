# Query engine status

The API's query route and `src/query/router.py`, `rewriter.py`, and cache module are zero-byte files. There is no query classifier, decomposition, rewrite, or application-level scope validation.

Do not send a query to `LLMClient` directly and call it RAG; it has no retrieval evidence by itself. A future query entry point must validate caller scope, query text/size, data access, deadlines, and cancellation before retrieval.
