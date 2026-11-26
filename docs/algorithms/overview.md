# Algorithms in the current repository

## Present algorithms

- **Page classification:** extracted-text length threshold in `pdf_intelligence.classify_page()`.
- **Chunking:** repeated-line frequency filter, heading-level heuristic, paragraph/character splitting, table/code detection, and deterministic hashing in `chunker.py`.
- **Priority:** filename-pattern classification in `watcher.classify_priority()` and a min-heap ordering by integer priority/counter.
- **Keyword ranking:** OpenSearch's BM25 implementation through `BM25Store.search()`.
- **Structured table classification:** simple string heuristics in `index_builder.infer_table_kb_type()`.

## Not present

No embeddings/vector similarity, hybrid rank fusion, reranking, knowledge-graph entity resolution, query decomposition, or claim-verification algorithm is implemented. Historical commit messages and placeholder module names do not change that status.
