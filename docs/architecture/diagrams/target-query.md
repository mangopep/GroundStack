# Proposed query sequence

```mermaid
sequenceDiagram
  actor Client
  participant API as Authenticated API (future)
  participant Use as Query use case (future)
  participant Search as BM25 + vector adapters (future)
  participant Rank as Fusion/reranking (future)
  participant LLM as Provider adapter (future)
  participant Verify as Claim verifier (future)
  Client->>API: question + collection scope
  API->>Use: validated principal and query
  Use->>Search: scoped lexical and semantic searches
  Search-->>Use: candidate passages with provenance
  Use->>Rank: fuse, filter, rerank
  Rank-->>Use: evidence within token budget
  Use->>LLM: prompt plus untrusted evidence block
  LLM-->>Use: draft claims and references
  Use->>Verify: validate source and claim support
  Verify-->>API: answer, citations, uncertainty/abstention
  API-->>Client: typed response
```

Every participant above is proposed except the standalone BM25 adapter and Ollama wrapper. Authorization, fusion, generation orchestration, and verification are absent today.
