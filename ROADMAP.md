# Roadmap

Priorities are ordered by dependency and risk. No item below should be read as implemented unless marked complete.

## P0 — Establish a trustworthy baseline

- [ ] Remove development credentials from tracked Compose configuration and validate required secrets.
- [ ] Reconcile dependency declarations with imports; lock and audit reproducible dependency sets.
- [ ] Run unit tests in a clean Python 3.11+ environment and repair failures.
- [ ] Define ingest metadata/version lifecycle and idempotent deletion behavior.
- [ ] Provide service-independent health/readiness semantics and structured request IDs.

## P1 — Deliver a vertical slice

- [ ] Wire file upload/ingestion job to parser, chunker, index, and status endpoint.
- [ ] Implement one embedding provider and vector backend behind typed interfaces.
- [ ] Wire retrieval and answer generation with page citations and abstention.
- [ ] Add real service-backed end-to-end tests and restart/recovery coverage.

## P2 — Make evidence quality measurable

- [ ] Curate a redistributable evaluation corpus and deterministic relevance labels.
- [ ] Measure Recall@K, MRR, nDCG, citation correctness, evidence coverage, latency, and memory.
- [ ] Add conflict handling and human corrections with provenance/audit history.
- [ ] Threat-model prompt injection and test tenant/document isolation.

## P3 — Operational profiles

- [ ] Define and measure a constrained local profile on Apple Silicon 8 GB.
- [ ] Harden standard Compose configuration, health ordering, resource bounds, and shutdown.
- [ ] Specify production deployment, backup/restore drills, migration policy, and monitoring.
- [ ] Add release, dependency update, vulnerability scan, and secret scan automation.

## Later

- [ ] Knowledge graph construction and entity resolution after evidence-grounded retrieval is stable.
- [ ] Optional web interface after the API contract and access control are established.
