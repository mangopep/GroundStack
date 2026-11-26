# Installation

## Python environment

From the repository root:

```bash
make setup
```

This creates `.venv`, installs the hash-locked application, development, and docs dependencies, then installs the local package without resolving a second dependency set. It includes Docling, OCR, PyTorch, and related packages, so it is a large install; no 8 GB memory or disk benchmark has been measured. If setup fails, confirm Python 3.11.5 or newer and a working package index, then inspect the exact first resolver/download error. Repeat the command to resume. It changes only `.venv` and package caches; remove `.venv` only if you intentionally want to discard the environment.

## Local service configuration

1. Preserve any existing `.env` file. If none exists, copy `.env.example` to `.env`.
2. Replace the sample secret values with unique random values.
3. Verify all required Compose variables are present without printing their values.
4. Start services only after reviewing `docker compose config` and the [data-loss warning](../infrastructure/docker.md#opensearch-initialization-warning).

```bash
# Safe to run only if .env does not already exist
# Safe to run only if .env does not already exist
test -f .env || cp .env.example .env
# Review service interpolation before starting
docker compose config --quiet
```

The current host's `.env` lacked values required by the current Compose file, so `docker compose config` failed during the audit. Existing containers were running; they were not recreated or stopped.

## Documentation preview

The docs toolchain is included in `make setup`. Preview with `make docs` or `.venv/bin/zensical serve`. Do not run `zensical gh-deploy` locally; publication is controlled by the [Actions workflow](../infrastructure/cicd.md) and still requires repository configuration.
