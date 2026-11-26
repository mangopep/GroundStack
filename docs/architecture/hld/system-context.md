# HLD: System context

## Current actors and external systems

- **Operator:** runs scripts, starts services, and places test PDFs in a watched folder.
- **FastAPI client:** can request a root message or process health. There is no document/query API.
- **PDF parser:** Docling converts native documents; PyMuPDF classifies pages and supplies fallback text.
- **Persistence services:** PostgreSQL/AGE, OpenSearch, MinIO, Redis, and Langfuse are declared in Compose. Only selected stores are called by the ingestion path.
- **Ollama:** host process for `LLMClient`; no query endpoint invokes the client.

## Current context diagram

```mermaid
C4Context
  title Current GroundStack context (simplified)
  Person(op, "Operator", "Starts scripts and places test PDFs")
  System(gs, "GroundStack code", "PDF ingestion, chunking, stores, basic API")
  System_Ext(pg, "PostgreSQL + AGE", "Metadata and structured records")
  System_Ext(os, "OpenSearch", "Lexical index")
  System_Ext(minio, "MinIO", "Source PDFs")
  System_Ext(redis, "Redis", "Cost tracker support; queue is in memory")
  System_Ext(ollama, "Ollama", "LLM client available, not wired to query")
  System_Ext(lf, "Langfuse", "Optional traces/events")
  Rel(op, gs, "runs watcher/API")
  Rel(gs, pg, "metadata and structured writes")
  Rel(gs, os, "chunk indexing and lexical search adapter")
  Rel(gs, minio, "document object operations")
  Rel(gs, redis, "cost tracking; no durable task queue")
  Rel(gs, ollama, "LLM wrapper calls when directly used")
  Rel(gs, lf, "optional tracing/events")
```

The diagram uses current code relationships, not proof that all external calls were exercised together. The task queue is an in-process Python heap, not Redis.
