# Testing strategy and baseline

## Existing suites

- Unit tests cover chunker, BM25 adapter behavior, DocStore with mocks, index builder, queue, worker, watcher, and structured KB conversion/queries.
- Integration tests cover PDF robustness, queue behavior, PostgreSQL, and MinIO.
- Evaluation harness files exist under `tests/eval/`, but the harness is not a benchmark report.

## Audit baseline and recovery verification

Before behavior changes, `.venv/bin/python -m pytest -q` reported **257 passed, 12 skipped, 11 dependency warnings** on Python 3.11.15 / pytest 9.2.0. All 12 skips came from the MinIO integration test module's service reachability guard. The test run did not execute a full real-stack ingestion-to-query scenario.

After the OpenSearch and queue regressions were fixed, the same command reported **260 passed, 12 skipped, 11 dependency warnings**. Three new tests assert existing indexes are preserved, missing indexes are created, and missing ingestion imports propagate. The 12 MinIO skips and absence of full-stack E2E remain.

Additional local gates pass: `ruff check .`, `ruff format --check src scripts tests`, strict mypy on `src/config/settings.py` and the three schema modules, `pip-audit --requirement requirements-lock.txt --disable-pip`, and `actionlint .github/workflows/*.yml`. The strict documentation build also passes. These local results do not substitute for a successful GitHub Actions run.

## Required next tests

1. Integration: parser → chunker → OpenSearch/PG/MinIO using an isolated disposable environment.
2. Recovery: injected failure after each store write, retry, process restart, reindex, and delete.
3. Query quality: labeled corpus and Recall@K/MRR/nDCG, citation correctness/coverage, abstention, p95 latency, and peak memory.
4. Security: malformed files, prompt injection, authorization, and tenant isolation once implemented.

Report exact commands and skipped-service reasons. Mocks prove unit behavior only.
