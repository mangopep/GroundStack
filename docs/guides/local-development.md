# Local development

Use Python 3.11+, create an isolated virtual environment, install `.[dev]`, and run Ruff and pytest. Service-backed integration tests need Docker Compose services. The repository currently has no lockfile, so dependency resolution is not yet reproducible. Do not use `make reset` unless you intend to delete all Compose volumes.
