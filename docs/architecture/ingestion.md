# Ingestion architecture

## Present path

The repository contains PDF intelligence, chunking, quality-gate, deduplication, index-builder, watcher, and worker modules. A worker delegates file processing to the ingestion pipeline and interacts with stores. This is not yet exposed through a working HTTP ingestion route; service-backed execution must be tested before relying on it.

```mermaid
sequenceDiagram
  participant F as File/watcher
  participant Q as Task queue
  participant W as Ingest worker
  participant P as Parser/chunker
  participant I as Index builder
  participant S as Search/object/SQL stores
  F->>Q: enqueue document task
  Q->>W: dispatch task
  W->>P: parse and create chunks
  P-->>W: pages, hierarchy, content
  W->>I: validate and index
  I->>S: persist document and records
  S-->>W: status
```

The sequence represents intended calls inferred from existing modules; verify exact adapters and side effects before treating it as a production execution trace.

## Target requirements

Use content hashes for idempotency; record source version, parser version, chunker version, tenant/collection, and page provenance. Make each job resumable with explicit states and bounded retries. Persist a manifest so deletion and reindexing can reconcile all stores. Never mark a document complete until every required write is confirmed or compensated.

OCR, table/image extraction, command fidelity, interruption recovery, and duplicate behavior require representative fixture-based tests. Current test names cover some PDF robustness and chunking cases, but no complete real-stack validation was performed in this audit.
