# Engineering standards

These rules apply to future changes in this repository. Read `docs/project/current-state.md` before changing architecture; that report separates verified behavior from placeholders and planned work.

## General

- Keep changes focused, preserve user data and existing working behavior, and explain material compatibility changes.
- Use clear names, small functions, explicit types at module boundaries, and validated Pydantic models for external input.
- Keep configuration at the boundary; do not read environment variables throughout business logic.
- Prefer dependency injection when it improves test isolation or makes a real boundary replaceable. Do not add abstractions without a concrete use case.
- Handle errors explicitly. Never return success after a failed import, store write, parse, or model call. Do not hide failures behind broad exception handlers or silent fallbacks.
- Do not commit secrets, personal source documents, model files, generated indexes, or database dumps. Preserve ignored user data.
- Avoid magic values. Name operational limits and document why they are chosen.
- Keep side effects visible and idempotent where retries are possible. Do not delete/recreate user indexes as part of normal startup.
- Separate current behavior from proposed architecture in code comments and documentation.

## Module boundaries

- `src/api`: HTTP transport and request/response validation. It must call application use cases rather than own storage logic.
- `src/ingestion`: parsing, page results, chunking, and indexing orchestration.
- `src/workers`: job lifecycle and asynchronous dispatch. A worker must not mark a task successful unless its handler completed real work.
- `src/stores`: adapters around external persistence systems.
- `src/schemas`: shared validated data contracts.
- `src/config`: validated settings and secret references.

Do not make API, worker, and store modules import one another in cycles. Introduce a narrow contract only when a real integration needs it.

## Reliability and security

- Validate document size, type, and path before processing. Treat document text as untrusted input.
- Enforce authorization before retrieval and again at persistence boundaries when multi-user support is introduced.
- Make the authoritative data owner and cross-store recovery path explicit before adding a new store.
- Preserve source identity, version, page, and chunk provenance through every transformation.
- Use bounded retries only for retryable failures; retries must be idempotent and observable.
- Do not log credentials, document content, prompts containing private data, or raw model responses by default.

## Tests and docs

- For each behavior change, define acceptance criteria, add focused regression coverage, run the relevant tests, inspect results, and update the relevant documentation.
- Distinguish unit, service-backed integration, and end-to-end evidence. Mocks do not prove service integration.
- Keep test runs deterministic and isolate environment variables, files, clocks, and external services.
- Build the documentation portal in strict mode and fix broken local references before merging docs changes.
- Report checks that could not run as `NOT TESTED`, with the concrete reason.

## Code quality

- Follow Ruff's configured Python 3.11 style. CI checks lint across the repository and formatting in `src/`, `scripts/`, and `tests/`. Keep those checks clean; do not apply repository-wide autoformatting without reviewing the resulting diff.
- Add type annotations to public functions and adapter contracts. Keep static type checks scoped to code that has been brought into compliance, then expand the checked surface deliberately.
