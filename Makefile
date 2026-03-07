.PHONY: dev stop reset init app test golden ingest backup install format lint help

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
	pytest tests/ -v

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

# Install dependencies
install:
	pip install -e .

# Format code
format:
	ruff format .

# Lint code
lint:
	ruff check .

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
	@echo "  make format  - Format code"
	@echo "  make lint    - Lint code"

