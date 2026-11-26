# LangFuse Setup Guide

LangFuse provides observability for your LLM calls - tracking prompts, responses, latency, and costs.

## 📝 Note: LangFuse is Optional

The RAG platform will work **without** LangFuse. If you skip this setup:
- ✅ All functionality works normally
- ❌ No LLM call tracing/observability
- ❌ No cost tracking visualization
- ❌ No prompt history

## 🚀 Quick Setup (5 minutes)

### Step 1: Start LangFuse

LangFuse is already running in Docker. Verify:

```bash
docker compose ps | grep langfuse
```

You should see:
```
rag-langfuse    Up    0.0.0.0:3000->3000/tcp
```

### Step 2: Access LangFuse UI

Open in your browser:
```
http://localhost:3000
```

### Step 3: Create Account

1. Click **"Sign Up"**
2. Fill in:
   - **Email**: your-email@example.com
   - **Password**: (choose a secure password)
   - **Name**: Your Name
3. Click **"Create Account"**

### Step 4: Create a Project

After signing in:

1. You'll see a welcome screen
2. Click **"Create Project"** or **"New Project"**
3. Enter project details:
   - **Project Name**: `RAG Platform`
   - **Description**: `Production RAG system with hybrid retrieval` (optional)
4. Click **"Create"**

### Step 5: Get API Keys

1. After creating the project, you'll be on the project dashboard
2. Click on **"Settings"** (gear icon) in the left sidebar
3. Click on **"API Keys"** tab
4. You should see two keys already created:
   - **Public Key** (starts with `pk-lf-`)
   - **Secret Key** (starts with `sk-lf-`)

5. Copy both keys (click the copy icon next to each)

### Step 6: Update .env File

Open your `.env` file and update these lines:

```bash
# LangFuse
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=pk-lf-xxxxxxxxxxxxxxxxxxxxxxxx
LANGFUSE_SECRET_KEY=sk-lf-xxxxxxxxxxxxxxxxxxxxxxxx
```

**Important**: Replace the `xxxxx` with your actual keys!

### Step 7: Restart Services

For the keys to take effect:

```bash
# Stop services
make stop

# Start services
make dev
```

## ✅ Verify Setup

### Test LLM Client with Tracing

```python
from src.llm.client import get_llm_client
import asyncio

async def test():
    client = get_llm_client()
    response = await client.generate(
        prompt="What is RAG?",
        system_prompt="You are a helpful AI assistant."
    )
    print(response)

asyncio.run(test())
```

### Check LangFuse Dashboard

1. Go to http://localhost:3000
2. Click on your project "RAG Platform"
3. Click on **"Traces"** in the left sidebar
4. You should see a trace named `llm_generation` with:
   - Input prompt
   - Output response
   - Latency
   - Token counts

## 📊 What You'll See in LangFuse

### Traces
Every LLM call is logged as a trace:
- **Query Rewriter**: When queries are rewritten
- **Answer Generator**: When answers are generated
- **Verifier**: When answers are verified
- **Confidence Scorer**: When confidence is calculated

### Metrics
- **Total Calls**: Number of LLM invocations
- **Latency**: P50, P95, P99 latencies
- **Token Usage**: Input/output tokens per call
- **Cost**: Estimated cost (for paid APIs)

### Prompt Management
- View all prompts used
- Compare different versions
- Track prompt performance

## 🔧 Advanced Configuration

### Production Setup

For production, you'd typically use LangFuse Cloud instead of self-hosted:

1. Sign up at https://cloud.langfuse.com
2. Create a project
3. Get API keys
4. Update `.env`:
   ```bash
   LANGFUSE_HOST=https://cloud.langfuse.com
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```

### Multiple Environments

Create separate projects for each environment:
- `RAG Platform - Development`
- `RAG Platform - Staging`
- `RAG Platform - Production`

Use different API keys in each `.env` file.

## 🐛 Troubleshooting

### LangFuse not accessible at localhost:3000

```bash
# Check if container is running
docker compose ps | grep langfuse

# Check logs
docker compose logs langfuse

# Restart LangFuse
docker compose restart langfuse
```

### "Invalid API keys" error

1. Double-check you copied the entire key (including `pk-lf-` or `sk-lf-` prefix)
2. Ensure no extra spaces or newlines
3. Restart services after updating `.env`

### No traces appearing

1. Verify keys are correctly set in `.env`
2. Check that services were restarted after updating `.env`
3. Look for errors in application logs:
   ```bash
   docker compose logs rag-langfuse
   ```

### Database connection error

LangFuse uses the same PostgreSQL database. If you see connection errors:

```bash
# Restart PostgreSQL
docker compose restart postgres

# Restart LangFuse
docker compose restart langfuse
```

## 📚 Resources

- **LangFuse Docs**: https://langfuse.com/docs
- **LangFuse GitHub**: https://github.com/langfuse/langfuse
- **Python SDK**: https://langfuse.com/docs/sdk/python

## 🎯 Next Steps

Once LangFuse is set up:

1. ✅ All LLM calls are automatically traced
2. 📊 View real-time metrics in dashboard
3. 🔍 Debug slow queries by inspecting traces
4. 💰 Track token usage and optimize costs
5. 📈 Compare prompt versions and performance

---

**That's it! LangFuse is now tracking all your LLM interactions.**

Return to the main [README](https://github.com/mangopep/rag_platform#readme) to continue with the Week 1 setup.
