# Consistency and failure windows

Ingestion writes to multiple independent services with no distributed transaction:

1. OpenSearch chunk writes and PostgreSQL structured record writes happen in the loop.
2. MinIO source upload follows the loop.
3. PostgreSQL document metadata is written last.

If a later step fails, earlier writes remain. The returned `partial` status covers chunk/table errors, but some object/metadata errors raise after those earlier writes. No outbox, transaction coordinator, or reconciliation command currently restores a consistent state.

Target design: PostgreSQL manifest owns document version/job status; storage/index adapters are idempotent derived materializations; persist an outbox/retry state; reconcile by manifest; and define deletion to tombstone then remove every derived object. This target is not implemented.
