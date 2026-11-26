# Architecture overview

This page separates current implementation from target design. Solid edges are current only when called by the checked source path; dashed edges are proposed.

## Current implementation

```mermaid
flowchart TD
  Fs[Watched filesystem folder] --> W[IngestionWatcher]
  W --> B[ingest_pdf]
  B --> P[Docling + PyMuPDF parser]
  P --> C[Hierarchy-aware chunker]
  C --> O[(OpenSearch BM25)]
  C --> H[(PostgreSQL structured KB heuristics)]
  B --> M[(MinIO source PDF)]
  B --> D[(PostgreSQL document metadata)]
  B -. optional event .-> LF[Langfuse]
  API[FastAPI: process endpoints only] --> UI[Static workspace preview]
  Q[BM25Store.search] -. no query route calls it .-> O
  L[Ollama LLMClient] -. no application flow calls it .-> Ollama[Ollama host]
```

## Proposed target boundary

```mermaid
flowchart LR
  Client --> API[Authenticated API]
  API --> UC[Application use cases]
  UC --> Manifest[(PostgreSQL manifest)]
  UC --> Jobs[Durable job adapter]
  Jobs --> Ingest[Versioned ingest pipeline]
  Ingest --> Parser[Parser port]
  Ingest --> Lexical[(BM25 adapter)]
  Ingest --> Vector[(Embedding + vector adapter)]
  Ingest --> Object[(Object adapter)]
  Ingest --> Graph[(Optional graph adapter)]
  UC --> Query[Scoped query use case]
  Query --> Retrieve[Lexical + vector + optional graph]
  Retrieve --> Fuse[RRF + measured reranking]
  Fuse --> Context[Budgeted evidence context]
  Context --> Model[Provider-neutral LLM]
  Model --> Verify[Claim/source checks + abstention]
  Verify --> Client
```

Dashed/target components are design directions only. For current truth, see the [status matrix](../project/implementation-status.md).
