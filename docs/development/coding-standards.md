# Coding standards

The repository-level [CLAUDE.md](https://github.com/mangopep/rag_platform/blob/main/CLAUDE.md) is the engineering rule set. Key requirements: keep module boundaries explicit, validate external inputs, keep errors visible, avoid false-success placeholders, preserve provenance, make retries idempotent, and update tests/docs with behavior.

The pre-recovery Ruff baseline had 81 findings and 43 unformatted Python files. That cleanup is complete and the local checks pass. CI formats only `src/`, `scripts/`, and `tests/`; keep Markdown code examples readable without applying Python formatting to documentation pages.
