# Keyword search and BM25

BM25 is a lexical ranking function. It rewards query words that occur in a passage, with term frequency and document-length normalization. It is useful for exact names, identifiers, and commands, but can miss paraphrases and synonyms.

`src/stores/bm25.py` wraps OpenSearch's `multi_match` query and filters structural-only chunks. `search(query, top_k)` validates empty queries and positive `top_k`, then formats hits with chunk ID, title, content, score, section path, page, document ID, and chunk type. The current ingestion path has no API that calls this method.

The OpenSearch mapping initializer has a page-field mismatch: it declares singular `page_number`; the store writes/reads `page_numbers`. Test against a real index before relying on page attribution. Baseline integration tests did not establish this full path.
