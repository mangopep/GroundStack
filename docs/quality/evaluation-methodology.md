# Evaluation methodology

A benchmark report should pin the repository commit, Python/runtime, container image digests, model names and quantizations, corpus hashes/licenses, chunker/parser settings, query labels, hardware, Docker memory limits, concurrency, warm/cold cache state, and run count.

Measure retrieval Recall@K/MRR/nDCG; citation precision/correctness and evidence coverage; answer faithfulness and abstention with human review; ingestion pages/chunks per second; query p50/p95; CPU/RSS/container peak; and index/object/disk growth. Keep results and scripts versioned. Mark unavailable values NOT TESTED.
