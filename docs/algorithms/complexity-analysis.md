# Complexity analysis

These are code-level estimates, not performance measurements.

| Operation | Expected complexity | Notes |
|---|---|---|
| Path ID hash | O(path length), constant-size path in practice | Not a file-content hash |
| Page classification | O(total extracted page text) | PDF decode/Docling cost dominates |
| Repeated-line scan | Expected O(number of characters/lines) | Uses per-line page sets; memory scales with distinct lines |
| Chunk output | O(N + C) expected | N extracted text; C chunk count; local sorting of pages |
| Priority heap push/pop | O(log Q) | Q queued in-memory jobs |
| BM25 query | External-index dependent | OpenSearch corpus size, shard layout, and scoring dominate; not measured |
| Index writes | O(C) remote calls today | One call per indexed content chunk; not bulked |
| Graph/vector search | Not implemented | No complexity claim is possible |

No benchmark values are implied. See [benchmark methodology](../quality/benchmarks.md).
