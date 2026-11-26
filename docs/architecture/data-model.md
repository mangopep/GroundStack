# Data model and storage responsibilities

Current store modules cover selected structured records, document objects, BM25 index data, and graph access scaffolding. The exact schema and cross-store consistency contract are not yet documented as stable.

| Store | Intended responsibility | Current status |
|---|---|---|
| PostgreSQL | document manifests, structured records, audit/correction metadata | schema and store code exist; lifecycle contract incomplete |
| OpenSearch | lexical chunk index and metadata filters | BM25 store code exists |
| MinIO | original documents and derived assets | document store code exists |
| Redis | cache/session/queue acceleration | Compose service exists; durable job ownership is not proven |
| AGE | entity/relation graph | image enabled; end-to-end graph pipeline not implemented |
| pgvector | vector index | compatibility requested; not currently configured |

A future canonical manifest must identify all derived records to enable idempotent reindex, deletion, backup, and restore verification.
