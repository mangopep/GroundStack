# ADR 0002: Separate lexical index and canonical metadata

- Status: provisional
- Date: 2026-11-26

## Context

The repository includes OpenSearch BM25, PostgreSQL, MinIO, and Apache AGE-compatible setup. Their canonical ownership and consistency contract are incomplete.

## Decision

Treat PostgreSQL as the future canonical manifest/metadata store, MinIO as original/derived object storage, and OpenSearch as a rebuildable retrieval index. AGE and pgvector remain optional until a working use case and evaluation justify them.

## Alternatives

Store all content in one database, or adopt more systems immediately. Keeping the existing adapters is incremental; adding AGE/vector complexity without a measurable use case is not justified.

## Consequences

Cross-store writes require idempotency, reconciliation, and restore drills. This ADR describes target ownership; current runtime behavior may differ.
