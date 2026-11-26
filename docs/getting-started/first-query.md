# First query: not available yet

There is no query endpoint or complete query orchestration. `BM25Store.search()` is a callable lexical adapter, not a product query flow: it requires a live OpenSearch index and returns ranked chunk dictionaries. No embedding, hybrid rank fusion, answer generation, claim checking, or citation response is connected.

Use the [keyword search explanation](../fundamentals/keyword-search.md) to inspect the adapter. Do not send private documents to an external model while experimenting; no answer endpoint exists here.
