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
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
ruff check .
ruff format --check .
pytest
```

Service-backed tests require the documented Compose services. State clearly which tests ran and which were skipped. Do not describe mocks as integration evidence.

## Pull requests

Include motivation, implementation summary, test commands and results, compatibility notes, documentation changes, and known limitations. Avoid unrelated formatting churn. Use conventional commit messages where practical; releases will follow semantic versioning once release automation exists.

Good first contributions include adding unit coverage for a documented edge case, fixing stale setup instructions, or improving error messages without changing external behavior.
