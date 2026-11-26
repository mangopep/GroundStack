# Contributing

Thanks for helping improve GroundStack. The project is experimental, so contributions should distinguish observed behavior from intended design.

## Before opening a change

1. Search existing issues and open a focused issue for substantial behavior or architecture changes.
2. Keep changes small and preserve unrelated work.
3. Do not add real documents, secrets, generated indexes, database dumps, or model artifacts.
4. For new dependencies, explain the responsibility, alternatives, license, supported Python/ARM64 platforms, and measurable benefit.
5. Update the relevant guide and implementation status when behavior changes.

## Development

```bash
make setup
make lint
make typecheck
make security
make test
make integration
make docs
```

`make setup` requires Python 3.11.5 or newer. `make integration` starts and removes its own disposable service stack; do not manually point service tests at personal or production data. `make docs` also requires Docker to run the pinned Mermaid CLI. State clearly which tests ran and which were skipped. Do not describe mocks as integration evidence.

## Pull requests

Include motivation, implementation summary, test commands and results, compatibility notes, documentation changes, and known limitations. Avoid unrelated formatting churn. Use conventional commit messages where practical. Release candidates use semantic versions and the approval-gated process in `docs/infrastructure/release.md`; do not publish or create a release as part of an ordinary pull request.

Good first contributions include adding unit coverage for a documented edge case, fixing stale setup instructions, or improving error messages without changing external behavior.
