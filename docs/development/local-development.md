# Local development

1. Use Python 3.11+ and create `.venv`.
2. Install `.[dev]` from the repository root.
3. Keep existing `.env` and `data/` contents. The `.gitignore` excludes local secrets and corpus files.
4. Run focused unit tests first, then service-backed tests only against a disposable/test database.
5. Avoid `make reset`: it runs `docker compose down -v` and deletes all named Compose volumes.

The checked-in dependency set is not locked. Record the Python version and actual installed versions when reporting a defect. Current baseline: 257 passed, 12 skipped on Python 3.11.15; see [test evidence](../quality/testing-strategy.md).
