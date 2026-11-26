# Document data lifecycle

Current lifecycle: a local path is parsed, chunks are indexed, selected table records are inserted, the source PDF is uploaded to MinIO, and metadata is upserted. A worker may set status and move local files after success/failure. There is no API deletion flow, retention policy, tenant owner, content-addressed source version, or cross-store reconciliation.

Deletion must eventually identify all chunk IDs, structured assertions, graph edges, source objects, and metadata for a specific version, enforce authorization, and leave an auditable tombstone. Until that contract exists, there is no documented safe product-level delete command.
