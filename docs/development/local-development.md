# Local development

1. Use Python 3.11.5 or newer and create `.venv`.
2. Run `make setup` from the repository root to install the hash-locked development, ingestion, and documentation dependencies.
3. Keep existing `.env` and `data/` contents. The `.gitignore` excludes local secrets and corpus files.
4. Run `make test` for the regular suite and `make integration` for real service tests against a per-run disposable stack. The integration command selects dynamic loopback ports and removes only its own test containers and volume.
5. Avoid `make reset`: it runs `docker compose down -v` and deletes all named Compose volumes.

Install the reproducible development and ingestion dependency set with `python -m pip install --require-hashes -r requirements-lock.txt`. Record the Python version when reporting a defect. Historical baseline and current service-integration evidence are in [test evidence](../quality/testing-strategy.md).
