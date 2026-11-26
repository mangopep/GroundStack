# Algorithm decisions and constraints

The code uses simple heuristics where they already exist: file-name priorities, text-length page classification, character-based token estimation, table-type string matching, and OpenSearch BM25. These are easy to inspect but can fail on layout variation, different tokenization, and semantic paraphrase.

The current first improvement should preserve those baselines while adding labeled regression fixtures. Do not introduce embeddings or a reranker solely because they are common in RAG architectures; compare retrieval quality and resource cost on the same corpus first. RRF is a reasonable future baseline because it combines ranks without requiring BM25/vector scores to share a scale, but it is not in this repository.
