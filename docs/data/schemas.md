# Data schemas

## PostgreSQL

`scripts/init_db.sql` declares:

- `structured_kb`: text ID/type, version, JSONB data, chunk hash, created/updated timestamps, creator, JSONB tags.
- `human_overrides`: topic hash, JSONB correction, status/vote count, timestamps, creator.
- `document_metadata`: path-derived `doc_id`, filename/source type, page/chunk counts, MinIO path, version, ingestion timestamp.
- `config` and `user_feedback` tables.
- GIN indexes on selected JSONB fields, B-tree on type, and partial index for active overrides.

There is no versioned migration history. `document_metadata` currently lacks content hash, tenant/collection, parser/chunker version, job state, failure details, and source checksum.

## OpenSearch

`BM25Store` serializes chunk ID, document ID, title, content, section path, page numbers, chunk type, parent ID, and structural flag. `scripts/init_opensearch.py` has an older/inconsistent mapping including singular `page_number`, version, chunk hash, and ingest date. Mapping drift requires a migration/initializer fix.

## Object storage

MinIO stores original PDFs and images using document identifiers/bucket names. It is not the canonical lifecycle manifest. No retention/versioning policy is configured here.

## Vector and graph data

No active vector schema or graph traversal model exists. AGE is initialized but no current graph data contract is defined.
