.PHONY: dev stop reset init app test golden ingest backup setup install format lint typecheck security build smoke integration docs clean help

PYTHON := .venv/bin/python
RUFF := .venv/bin/ruff
MYPY := .venv/bin/mypy
PIP_AUDIT := .venv/bin/pip-audit
ZENSICAL := .venv/bin/zensical

# Default target
all: dev

# Start all services in development mode
dev:
	docker compose up -d
	@echo "Starting Ollama server in background..."
	ollama serve &

# Stop all services
stop:
	docker compose down

# Stop all services and remove volumes
reset:
	docker compose down -v

# Initialize OpenSearch and MinIO
init:
	python scripts/init_opensearch.py
	python scripts/init_minio.py

# Run the API application
app:
	uvicorn src.api.main:app --reload --port 8000

# Run tests
test:
	$(PYTHON) -m pytest -q --cov=src --cov-report=term-missing --cov-fail-under=75

# Install the hash-locked application and docs toolchains
setup:
	python3.11 -m venv .venv
	$(PYTHON) -m pip install --require-hashes -r requirements-lock.txt -r requirements-docs.txt
	$(PYTHON) -m pip install --no-deps -e .

# Run golden tests
golden:
	python scripts/run_golden_tests.py

# Run document ingestion watcher
ingest:
	python -m src.ingestion.watcher --path data/corpus/

# Backup PostgreSQL database
backup:
	pg_dump -h localhost -U rag -d rag_platform -f data/backups/$$(date +%Y%m%d_%H%M%S)_rag_platform.sql
	@echo "Backup created successfully"

# Backward-compatible setup target
install: setup

# Format code
format:
	$(RUFF) format src scripts tests

# Lint code
lint:
	$(RUFF) check .

# Type-check validated configuration and schema boundaries strictly
typecheck:
	$(MYPY) --strict src/config/settings.py src/schemas/query.py src/schemas/response.py src/schemas/knowledge.py

# Audit exact, hash-locked package versions without installing dependencies again
security:
	$(PIP_AUDIT) --requirement requirements-lock.txt --disable-pip
	$(PYTHON) -m bandit --quiet --recursive src

# Build the Python wheel
build:
	$(PYTHON) -m pip wheel --no-deps --wheel-dir dist .

# Verify API process and static workspace are reachable; start `make app` first
smoke:
	curl --fail --silent --show-error --output /dev/null http://127.0.0.1:8000/health
	curl --fail --silent --show-error --output /dev/null http://127.0.0.1:8000/workspace/
	@echo "API health and workspace returned HTTP 200"

# Service-backed tests; configure and start the required services first
integration:
	./scripts/run_integration.sh

# Strictly build the documentation site
docs:
	$(ZENSICAL) build --strict
	$(PYTHON) scripts/check_mermaid.py

# Remove generated build/test outputs only; Docker data volumes are untouched
clean:
	rm -rf build dist site .pytest_cache .ruff_cache src/groundstack.egg-info

# Show help
help:
	@echo "Available targets:"
	@echo "  make dev     - Start all services in development mode"
	@echo "  make stop    - Stop all services"
	@echo "  make reset   - Stop all services and remove volumes"
	@echo "  make init    - Initialize OpenSearch and MinIO"
	@echo "  make app     - Run the API application"
	@echo "  make test    - Run tests"
	@echo "  make golden  - Run golden tests"
	@echo "  make ingest  - Run document ingestion watcher"
	@echo "  make backup  - Backup PostgreSQL database"
	@echo "  make install - Install dependencies"
	@echo "  make setup   - Install hash-locked app and docs dependencies"
	@echo "  make format  - Format code"
	@echo "  make lint    - Lint code"
	@echo "  make typecheck - Strictly type-check configuration and schemas"
	@echo "  make security - Audit the hash-locked dependencies"
	@echo "  make build   - Build a Python wheel"
	@echo "  make smoke   - Check API health and workspace routes"
	@echo "  make integration - Run service-backed tests"
	@echo "  make docs    - Strict documentation build"
	@echo "  make clean   - Remove generated outputs"

