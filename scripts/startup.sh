#!/bin/bash
# Startup script for RAG Platform - Week 1
# Run this after Docker Desktop is started

set -e  # Exit on error

echo "🚀 RAG Platform - Startup Script"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for a service
wait_for_service() {
    local name=$1
    local url=$2
    local max_attempts=30
    local attempt=1

    echo -n "⏳ Waiting for $name to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url" >/dev/null 2>&1; then
            echo -e " ${GREEN}✓${NC}"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    echo -e " ${RED}✗${NC}"
    echo "⚠️  $name failed to start within expected time"
    return 1
}

# Check prerequisites
echo "1️⃣  Checking prerequisites..."
echo ""

if ! command_exists docker; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker installed"

if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}✗ Docker daemon not running${NC}"
    echo "Please start Docker Desktop and try again"
    exit 1
fi
echo -e "${GREEN}✓${NC} Docker daemon running"

if ! command_exists ollama; then
    echo -e "${RED}✗ Ollama not found${NC}"
    echo "Please install Ollama: https://ollama.ai"
    exit 1
fi
echo -e "${GREEN}✓${NC} Ollama installed"

if ! command_exists python3; then
    echo -e "${RED}✗ Python3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python installed"

echo ""
echo "2️⃣  Starting Ollama server..."
echo ""

# Check if Ollama is already running
if pgrep -x "ollama" >/dev/null; then
    echo -e "${GREEN}✓${NC} Ollama already running"
else
    # Start Ollama in background
    ollama serve >/dev/null 2>&1 &
    sleep 3
    echo -e "${GREEN}✓${NC} Ollama server started"
fi

# A small model default for constrained local hosts. Override through OLLAMA_MODEL.
OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:1b}"

# Check if model is already pulled
echo ""
echo "3️⃣  Checking Ollama model..."
echo ""

if ollama list 2>/dev/null | grep -Fq "$OLLAMA_MODEL"; then
    echo -e "${GREEN}✓${NC} Model $OLLAMA_MODEL already available"
else
    echo "⏳ Pulling $OLLAMA_MODEL model (this may take several minutes)..."
    if ollama pull "$OLLAMA_MODEL"; then
        echo -e "${GREEN}✓${NC} Model pulled successfully"
    else
        echo -e "${YELLOW}⚠️  Model pull failed - you may need to do this manually${NC}"
        echo "Run: ollama pull $OLLAMA_MODEL"
    fi
fi

echo ""
echo "4️⃣  Starting Docker services..."
echo ""

# Start Docker Compose services
docker compose up -d

echo ""
echo "5️⃣  Waiting for services to be healthy..."
echo ""

# Wait for each service natively
echo -n "⏳ Waiting for PostgreSQL to be ready..."
for i in {1..30}; do
    if docker exec rag-postgres pg_isready -U rag >/dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

echo -n "⏳ Waiting for Redis to be ready........"
for i in {1..30}; do
    if docker exec rag-redis redis-cli ping >/dev/null 2>&1; then
        echo -e " ${GREEN}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
done

wait_for_service "OpenSearch" "http://localhost:9200" || true
wait_for_service "MinIO" "http://localhost:9000/minio/health/live" || true
wait_for_service "LangFuse" "http://localhost:3000" || true

echo ""
echo "6️⃣  Initializing infrastructure..."
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# Initialize OpenSearch
echo "⏳ Creating OpenSearch index..."
if python3 scripts/init_opensearch.py; then
    echo -e "${GREEN}✓${NC} OpenSearch initialized"
else
    echo -e "${YELLOW}⚠️  OpenSearch initialization failed${NC}"
fi

# Initialize MinIO
echo "⏳ Creating MinIO buckets..."
if python3 scripts/init_minio.py; then
    echo -e "${GREEN}✓${NC} MinIO initialized"
else
    echo -e "${YELLOW}⚠️  MinIO initialization failed${NC}"
fi

# Verify PostgreSQL tables
echo "⏳ Verifying PostgreSQL tables..."
if docker exec rag-postgres psql -U rag -d rag_platform -c "\dt" >/dev/null 2>&1; then
    echo -e "${GREEN}✓${NC} PostgreSQL tables created"
else
    echo -e "${YELLOW}⚠️  Could not verify PostgreSQL tables${NC}"
fi

echo ""
echo "=================================="
echo -e "${GREEN}✅ RAG Platform is ready!${NC}"
echo "=================================="
echo ""
echo "📊 Service Status:"
echo "  • PostgreSQL:  http://localhost:5432"
echo "  • OpenSearch:  http://localhost:9200"
echo "  • Redis:       http://localhost:6379"
echo "  • MinIO:       http://localhost:9000"
echo "  • MinIO UI:    http://localhost:9001 (credentials from .env)"
echo "  • LangFuse:    http://localhost:3000"
echo "  • Ollama:      http://localhost:11434"
echo ""
echo "📝 Next Steps:"
echo ""
echo "  1. Setup LangFuse:"
echo "     • Open http://localhost:3000"
echo "     • Create account and project"
echo "     • Copy keys to .env file"
echo "     • See docs/LANGFUSE_SETUP.md for detailed guide"
echo ""
echo "  2. Test ingestion:"
echo "     python scripts/seed_test_data.py"
echo ""
echo "  3. Start API server:"
echo "     make app"
echo ""
echo "  4. View service status:"
echo "     docker compose ps"
echo ""
echo "  5. Stop everything:"
echo "     make stop"
echo ""
