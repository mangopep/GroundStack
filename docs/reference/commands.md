# Command reference

Run commands from the repository root unless specified.

| Command | Effect and prerequisites | Side effects / undo |
|---|---|---|
| `.venv/bin/python -m pytest -q` | Runs all tests; Python env installed | May use already-running integration services; inspect test fixtures first |
| `.venv/bin/python -m uvicorn src.api.main:app --reload` | Starts local API on default port 8000 | Stop with Ctrl+C; no data writes from basic endpoints |
| `make setup` | Creates Python 3.11 `.venv`; installs hash-locked app, dev, and docs dependencies | Large download including OCR/ML libraries; only changes `.venv` and package cache |
| `make lint` | Runs Ruff lint from repository root | Read-only; resolves nonzero on findings |
| `make format` | Formats Python files under `src/`, `scripts/`, and `tests/` | Modifies those files; review with `git diff` |
| `make typecheck` | Runs strict mypy on config and schema boundaries | Read-only; currently checks four files |
| `make security` | Audits exact hashed versions in `requirements-lock.txt` | Network access to vulnerability data; does not install/upgrade packages |
| `make build` | Builds a wheel into `dist/` | Creates generated artifact; remove with `make clean` |
| `make smoke` | Checks `/health` and `/workspace/` | Requires `make app` running; read-only HTTP requests |
| `make integration` | Starts PostgreSQL/AGE, OpenSearch, Redis, and MinIO with fake credentials, then runs service-backed tests | Requires Docker and free disk/RAM; uses unique Compose project, random loopback ports, and throwaway volume; trap removes only its own resources |
| `make docs` | Strictly builds the docs site and renders every Mermaid diagram with the pinned CLI container | Requires Docker; generated site and temporary diagram renders only; remove site with `make clean` |
| `make clean` | Removes build/test/site output and package metadata | Does not remove Docker volumes, corpus, or backups |
| `docker compose config --quiet` | Validates Compose interpolation | Read-only; fails if required variables missing |
| `docker compose up -d` | Starts local service stack | Creates/starts named volumes and consumes disk/RAM |
| `docker compose down` | Stops and removes containers/network | Keeps named volume data |
| `docker compose down -v` / `make reset` | Stops stack and deletes named volume data | **DESTRUCTIVE: database/index/object/cache data loss** |
| `.venv/bin/zensical serve` | Local docs preview | Serves local static preview; stop with Ctrl+C |
| `.venv/bin/zensical build --strict` | Validates and builds docs | Writes generated site output; remove generated `site/` directory to clean |

`scripts/startup.sh` now uses create-only OpenSearch index initialization. It still has broader startup/readiness limitations; see [current state](../project/current-state.md) before running it against valuable data.

## Expected output and recovery

- `make setup`: package installer reports installed locked packages. A wheel/platform resolution failure commonly means the selected Python version or machine architecture lacks a compatible artifact; keep the error text and check the package's supported platform before changing versions.
- `make security`: `No known vulnerabilities found` or an advisory list with affected package and version. Update the source dependency or document a time-limited exception; do not suppress the scanner.
- `make build`: prints a `.whl` name under `dist/`. The build does not publish it. Remove it with `make clean`.
- `make smoke`: exits 0 after both HTTP 200 responses. If it fails, start the API with `make app`, check port 8000, then inspect server logs.
- `make integration`: tests may skip when a guarded external service is unavailable. A skipped service test is not integration evidence; check service status and test configuration before rerunning.
- `make docs`: exits nonzero for invalid links, navigation, Markdown configuration, or Mermaid syntax. Fix the referenced source Markdown and rerun; generated `site/` can be recreated at any time.
