# Benchmark status

**NOT TESTED:** retrieval Recall@K, MRR, nDCG, answer faithfulness, citation correctness, evidence coverage, abstention accuracy, ingestion throughput, query p50/p95, peak memory, and resource use on Apple Silicon M4 8 GiB.

The audit host reported 16 GiB physical RAM, Docker Linux/aarch64, and about 4.2 GiB free disk. A `docker stats` snapshot showed OpenSearch near its configured 1 GiB limit. These are environment observations, not product benchmark measurements. Reproducible methodology is in [evaluation methodology](evaluation-methodology.md).
