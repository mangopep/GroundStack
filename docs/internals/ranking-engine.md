# Ranking engine status

Current retrieval is OpenSearch BM25. The code includes no score normalization or cross-index fusion. `src/retrieval/reranker.py` is empty.

A future hybrid ranker should begin with a transparent baseline such as Reciprocal Rank Fusion: for each item, sum `1 / (k + rank)` across result lists. For lists of lengths `n` and `m`, merging is O(n + m) expected with a hash map, followed by O(u log u) sorting over `u` unique candidates. Measure Recall@K, MRR, nDCG and latency on held-out labels before selecting `k` or adding a model reranker. These are design notes, not current behavior.
