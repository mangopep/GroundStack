# Retrieval architecture

## Current state

OpenSearch BM25 code exists. Vector search and embeddings are not implemented as a complete path. Query rewriting, routing, retrieval fusion, reranking, context assembly, and response generation are not connected to the API.

## Proposed query flow

```mermaid
sequenceDiagram
  participant C as Client
  participant A as API/use case (proposed)
  participant R as Retriever (proposed)
  participant B as BM25 index
  participant V as Vector index
  participant G as Generator
  C->>A: question + scope
  A->>R: normalized query + authorized scope
  par lexical
    R->>B: BM25 search
  and semantic
    R->>V: vector search
  end
  R-->>A: fused/reranked passages with provenance
  A->>G: evidence within token budget
  G-->>A: answer claims and source references
  A-->>C: answer, citations, uncertainty
```

This is proposed architecture only. Scope filtering must happen inside each backend query, not after results are returned. Reciprocal Rank Fusion and reranking should be configurable and evaluated against a labeled corpus before becoming defaults.
