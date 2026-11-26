# Testing strategy and baseline

## Existing suites

- Unit tests cover chunker, BM25 adapter behavior, DocStore with mocks, index builder, queue, worker, watcher, and structured KB conversion/queries.
- Integration tests cover PDF robustness, queue behavior, PostgreSQL, and MinIO.
- Evaluation harness files exist under `tests/eval/`, but the harness is not a benchmark report.

## Audit baseline and recovery verification

Before behavior changes, `.venv/bin/python -m pytest -q` reported **257 passed, 12 skipped, 11 dependency warnings** on Python 3.11.15 / pytest 9.2.0. All 12 skips came from the MinIO integration test module's service reachability guard. The test run did not execute a full real-stack ingestion-to-query scenario.

After the OpenSearch and queue regressions were fixed, the local suite reported **260 passed, 12 skipped, 11 dependency warnings**. Three new tests assert existing indexes are preserved, missing indexes are created, and missing ingestion imports propagate. HTTP contract tests now cover the current FastAPI routes. Service-backed tests require `GROUNDSTACK_RUN_SERVICE_INTEGRATION=1` and disposable services; routine test runs do not write to a developer's default database or object store.

The clean hash-locked environment now includes `psycopg-pool` and `watchdog`, which earlier CI collection had exposed as missing declarations. `make integration` starts a uniquely named disposable PostgreSQL, OpenSearch, Redis, and MinIO stack on dynamically selected loopback ports, then removes only its own containers and volume. It completed **40 integration tests** and verified cleanup of test PostgreSQL rows and MinIO buckets. The normal unit run completed **248 passed, 29 skipped**; service-backed skips are expected unless the explicit isolated integration command is used.

The latest regular local suite measures **78.45% line coverage** across executable `src` statements. CI and `make test` require **75%**: this floor is 3.45 percentage points below the measured baseline to leave room for platform/service-dependent coverage while still failing a material regression. Service-backed tests are separately run against a disposable stack.

Additional local gates pass: `ruff check .`, `ruff format --check src scripts tests`, strict mypy on `src/config/settings.py` and the three schema modules, `pip-audit --requirement requirements-lock.txt --disable-pip`, Bandit on `src/`, and `actionlint .github/workflows/*.yml`. The strict documentation build also passes. The lock requires Python 3.11.5 or newer because Trivy identified vulnerable Soup Sieve versions in the former 3.11.0–3.11.4 resolution. These local results do not substitute for successful GitHub Actions runs on the pushed commit.

## Required next tests

1. Integration: parser → chunker → OpenSearch/PG/MinIO using an isolated disposable environment.
2. Recovery: injected failure after each store write, retry, process restart, reindex, and delete.
3. Query quality: labeled corpus and Recall@K/MRR/nDCG, citation correctness/coverage, abstention, p95 latency, and peak memory.
4. Security: malformed files, prompt injection, authorization, and tenant isolation once implemented.

Report exact commands and skipped-service reasons. Mocks prove unit behavior only.
