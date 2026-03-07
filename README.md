# RAG Platform - Week 1 Foundation

Production-grade RAG (Retrieval-Augmented Generation) platform with knowledge graph, vector search, and LLM integration.

## 🚀 Quick Start

### Prerequisites
- Docker Desktop (running)
- Python 3.11+
- Ollama ([install](https://ollama.ai))

### One-Command Startup
```bash
./scripts/startup.sh
```

This script will:
1. ✅ Check all prerequisites
2. ✅ Start Ollama server
3. ✅ Pull llama3.3:8b model
4. ✅ Start all Docker services
5. ✅ Initialize OpenSearch index
6. ✅ Create MinIO buckets
7. ✅ Verify PostgreSQL tables

---

## 🏗️ Architecture

### Services (Docker Compose)
| Service | Port | Description |
|---------|------|-------------|
| **PostgreSQL + Apache AGE** | 5432 | Graph database with vector extension |
| **OpenSearch** | 9200 | Full-text search and BM25 retrieval |
| **Redis** | 6379 | Caching and session storage |
| **MinIO** | 9000/9001 | Object storage for PDFs and images |
| **LangFuse** | 3000 | LLM observability and tracing |
| **Ollama** | 11434 | Local LLM inference (llama3.3:8b) |

### Database Schema
- `structured_kb` - Structured knowledge (RCA, CLI commands, configs)
- `human_overrides` - User corrections and feedback
- `document_metadata` - Ingested document tracking
- `config` - System configuration
- `user_feedback` - Query ratings and corrections
- `rag_knowledge` - Apache AGE graph for relationships

---

## 📁 Project Structure

```
rag-platform/
├── docker-compose.yml          # 5 services: PostgreSQL, OpenSearch, Redis, MinIO, LangFuse
├── .env                        # Environment configuration
├── pyproject.toml              # Python dependencies
├── Makefile                    # Common commands
│
├── data/
│   ├── corpus/                 # 📥 DROP PDFs HERE for ingestion
│   ├── test/                   # Test PDFs
│   ├── processed/              # Successfully processed files
│   ├── failed/                 # Files that failed quality gate
│   └── backups/                # Database backups
│
├── scripts/
│   ├── startup.sh              # 🚀 One-command startup
│   ├── init_db.sql             # PostgreSQL schema
│   ├── init_opensearch.py      # Create OpenSearch index
│   ├── init_minio.py           # Create MinIO buckets
│   └── seed_test_data.py       # Generate 5 sample PDFs
│
├── src/
│   ├── config/                 # Centralized settings (Pydantic)
│   ├── llm/                    # LLM client + cost tracker
│   ├── ingestion/              # Document parsing (Docling)
│   ├── retrieval/              # Hybrid retrieval (vector + BM25)
│   ├── query/                  # Query rewriting + routing
│   ├── answer/                 # Answer generation + verification
│   ├── stores/                 # Data stores (vector, KB, graph)
│   └── api/                    # FastAPI endpoints
│
└── tests/                      # Pytest tests
```

---

## 🛠️ Common Commands

### Service Management
```bash
make dev          # Start all services
make stop         # Stop all services
make reset        # Stop and remove all data volumes
make init         # Initialize OpenSearch + MinIO
```

### Development
```bash
make app          # Start FastAPI server (port 8000)
make test         # Run pytest tests
make ingest       # Start document watcher on data/corpus/
make backup       # Backup PostgreSQL database
```

### Code Quality
```bash
make format       # Format code with ruff
make lint         # Lint code with ruff
pre-commit run --all-files  # Run all pre-commit hooks
```

---

## 📊 Verify Services

### Check Docker Status
```bash
docker compose ps
```

Expected output:
```
NAME              STATUS              PORTS
rag-postgres      Up (healthy)        5432
rag-opensearch    Up (healthy)        9200
rag-redis         Up (healthy)        6379
rag-minio         Up (healthy)        9000, 9001
rag-langfuse      Up                  3000
```

### Test Connections
```bash
# PostgreSQL
docker exec -it rag-postgres psql -U rag -d rag_platform -c "\dt"

# OpenSearch
curl http://localhost:9200/_cluster/health

# Redis
docker exec -it rag-redis redis-cli ping

# MinIO
curl http://localhost:9000/minio/health/live

# Ollama
curl http://localhost:11434/api/tags
```

---

## 🔑 Setup LangFuse (Optional)

LangFuse provides observability for LLM calls. If you skip this, the system will work without tracing.

1. Open http://localhost:3000
2. Create account
3. Create project "RAG Platform"
4. Copy **Public Key** and **Secret Key**
5. Update `.env`:
   ```bash
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```
6. Restart services: `make stop && make dev`

---

## 📄 Test Ingestion

### Option 1: Use Sample PDFs
```bash
python scripts/seed_test_data.py
```

This creates 5 sample PDFs:
- `01_handbook.pdf` - Handbook with headings
- `02_tables.pdf` - Document with tables
- `03_cli_commands.pdf` - CLI commands reference
- `04_multicolumn.pdf` - Multi-column layout
- `05_scanned_reference.pdf` - Simulated scanned document

### Option 2: Drop Your Own PDFs
```bash
cp /path/to/your.pdf data/corpus/
python -m src.ingestion.watcher --path data/corpus/
```

The ingestion pipeline will:
1. Parse PDF with Docling
2. Extract chunks with hierarchy
3. Detect CLI commands and code blocks
4. Run quality gate checks
5. Store chunks in OpenSearch
6. Extract structured knowledge to PostgreSQL
7. Build graph relationships in Apache AGE

---

## 🔧 Configuration

All configuration is in [.env](.env). Key settings:

### Database
```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=rag
POSTGRES_PASSWORD=rag_dev_2026
POSTGRES_DB=rag_platform
```

### LLM
```bash
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.3:8b
```

### Retrieval
```bash
RERANKER_THRESHOLD=0.7          # Minimum reranker score
```

---

## 🧪 Testing

### Run All Tests
```bash
make test
```

### Run Specific Test
```bash
pytest tests/test_ingestion.py -v
pytest tests/test_retrieval.py::test_hybrid_search -v
```

---

## 📝 Next Steps (Week 2+)

- [ ] Implement query rewriter
- [ ] Add query router (vector vs KB vs graph)
- [ ] Build context assembler
- [ ] Add reranking with FlashRank
- [ ] Implement answer generator
- [ ] Add answer verifier
- [ ] Build Chainlit UI
- [ ] Add RAGAS evaluation
- [ ] Implement human-in-the-loop overrides

---

## 🐛 Troubleshooting

### Docker daemon not running
```bash
open -a Docker  # macOS
```

### Ollama not responding
```bash
killall ollama
ollama serve &
```

### Services not healthy
```bash
docker compose logs [service-name]
docker compose restart [service-name]
```

### Reset everything
```bash
make reset          # Remove all volumes
make dev            # Start fresh
make init           # Reinitialize
```

---

## 📚 Resources

- **Docling**: [PDF parsing](https://github.com/DS4SD/docling)
- **Apache AGE**: [Graph extension for PostgreSQL](https://age.apache.org/)
- **OpenSearch**: [Full-text search](https://opensearch.org/)
- **LangFuse**: [LLM observability](https://langfuse.com/)
- **Ollama**: [Local LLM inference](https://ollama.ai/)

---

## 📄 License

MIT License - see LICENSE file for details.
