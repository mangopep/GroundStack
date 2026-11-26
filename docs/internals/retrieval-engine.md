# Retrieval engine status

`BM25Store.search()` is implemented in `src/stores/bm25.py`. It sends an OpenSearch `multi_match` over title/content/text and excludes explicit structural-only records. Search output includes score and source metadata. It does not apply tenant authorization because multi-tenant auth is not implemented.

`src/retrieval/gateway.py`, `fallback.py`, `reranker.py`, and `context_builder.py` are empty. There is no hybrid search, RRF, query rewrite, reranking, evidence context assembly, or API-level retrieval path. A future gateway should accept an already-authorized scope and preserve document version/page/chunk metadata end to end.
