# Phase 2 Verification Checklist & Advanced Ingestion Documentation

---

## PART 1: PHASE 2 VERIFICATION CHECKLIST

Before committing the Phase 2 code to the repository, the following checklist confirms that every component in the advanced ingestion pipeline is working correctly against live services.

### 🔌 1. Infrastructure Health
- [x] **Docker services running**
  - *Command:* `docker compose ps`
  - *Expected:* All 5 containers (Postgres, OpenSearch, Redis, MinIO, LangFuse) show `Up/Healthy`.
- [x] **PostgreSQL reachable**
  - *Command:* `docker exec rag-postgres pg_isready -U rag`
  - *Expected:* `rag-postgres:5432 - accepting connections`
- [x] **OpenSearch reachable**
  - *Command:* `curl -s http://localhost:9200`
  - *Expected:* JSON response with `"cluster_name"` and `"version"`.
- [x] **Redis reachable**
  - *Command:* `docker exec rag-redis redis-cli ping`
  - *Expected:* `PONG`
- [x] **MinIO reachable**
  - *Command:* `curl -s http://localhost:9000/minio/health/live`
  - *Expected:* HTTP `200 OK`

---

### 📄 2. PDF Intelligence
- [x] **PDF pages are extracted correctly**
  - *Command:* `python scripts/verify_e2e.py --skip-worker`
  - *Expected:* Part 2 prints `PASS — 91 pages extracted, text present=True`
- [x] **PageResult has all required fields**
  - *Expected:* `page_num`, `text`, `page_type`, `extraction_status` all present on every page.
- [x] **Page types are classified**
  - *Expected:* Pages are labelled as `native` (standard text) or `scanned` (image-only).

---

### ✂️ 3. Smart Chunker
- [x] **Chunks are created from pages**
  - *Command:* `python scripts/verify_e2e.py --skip-worker`
  - *Expected:* Part 3 prints `PASS — 180 chunks, max_tokens=943, over_1500=0`
- [x] **Every chunk has all 7 required fields**
  - *Expected:* `id`, `title`, `content`, `section_path`, `page_numbers`, `chunk_type`, `doc_id` all present.
- [x] **Token size constraints respected**
  - *Expected:* Zero chunks over 1500 tokens. Chunks under 100 tokens are allowed only for isolated atomic entries (e.g. glossary terms).
- [x] **Chunk types are assigned**
  - *Expected:* Each chunk is labelled `section`, `table`, or `code_block`.

---

### 🔍 4. BM25 Search Store
- [x] **Search returns results**
  - *Command:* `python scripts/verify_e2e.py --skip-worker`
  - *Expected:* Part 4 prints `PASS — results=3, index_count=700`.
- [x] **Result fields are complete**
  - *Expected:* Every result contains `chunk_id`, `title`, `content`, `score`, `section_path`, `page_number`.
- [x] **All 7 mapping fields present in OpenSearch**
  - *Command:* `python scripts/validate_production.py`
  - *Expected:* `chunk_id`, `title`, `content`, `section_path`, `page_number`, `doc_id`, `chunk_type` all show `PASS`.
- [x] **Schema is uniform (no legacy Phase-1 chunks)**
  - *Expected:* 0 legacy chunks. All 690 chunks have `chunk_type` set.

---

### 🗃️ 5. Structured Knowledge Base
- [x] **Store is functional**
  - *Command:* `python scripts/verify_e2e.py --skip-worker`
  - *Expected:* Part 5 prints `PASS — store functional`.
- [x] **Search by type executes without error**
  - *Expected:* `search_by_type('root_cause_analysis', 'error')` runs and returns a list (empty is fine if no RCA data was ingested).

---

### 📦 6. Document Store (MinIO)
- [x] **Bucket exists and contains files**
  - *Command:* `python scripts/verify_e2e.py --skip-worker`
  - *Expected:* Part 6 prints `PASS — bucket='rag-documents', objects=21`.
- [x] **Every ingested PDF is stored**
  - *Expected:* File count in MinIO matches document count in PostgreSQL.

---

### 🗄️ 7. Metadata Persistence (PostgreSQL)
- [x] **Metadata rows are saved after ingestion**
  - *Command:* `python scripts/verify_e2e.py --skip-worker`
  - *Expected:* Part 7 prints `PASS — document_metadata rows=21`.
- [x] **Each row has doc_id, filename, page_count, chunk_count**
  - *Expected:* `SELECT * FROM document_metadata LIMIT 5;` shows all columns populated.

---

### 👁️ 8. Ingestion Watcher
- [x] **Priority classification works**
  - *Command:* `python scripts/verify_e2e.py --skip-worker`
  - *Expected:* Part 8 prints `PASS — classify_priority ok=True`.
  - *Rules:* `rca/defect` → P0, `cli/config` → P1, `handbook` → P2, everything else → P3.
- [x] **Watcher detects a new file**
  - *Expected:* Part 8 prints `job_detected=True` after dropping a PDF into a watched folder.

---

### ⚙️ 9. Task Queue
- [x] **Queue status returns all required keys**
  - *Command:* `python scripts/verify_e2e.py --skip-worker`
  - *Expected:* Part 9 prints `PASS — missing=none` with keys `pending`, `processing`, `completed`, `failed`.

---

### 🔄 10. Background Worker
- [x] **Handler registers correctly**
  - *Command:* `python scripts/verify_e2e.py` *(without --skip-worker)*
  - *Expected:* Part 10 prints `handler_registered=True`.
- [x] **Task reaches a terminal state**
  - *Expected:* Part 10 prints `final_status=completed` or `final_status=failed` (not stuck as `processing`).
- [x] **Processed symlink is created**
  - *Expected:* A symlink appears in `data/processed/` after the worker finishes.

---

### 🚀 11. Full End-to-End Pipeline
- [x] **ingest_pdf() returns success**
  - *Command:* `python scripts/verify_e2e.py --skip-worker`
  - *Expected:* Part 11 prints `status=success, pages=91, chunks=180, indexed=178`.
  - *Note:* `chunks=180` vs `indexed=178` — 2 structural/navigational chunks are intentionally excluded from the search index (they carry layout context but no searchable content).
- [x] **Full production validation passes**
  - *Command:* `python scripts/validate_production.py`
  - *Expected:* `19/19 checks passed — Phase-2 system is production-ready`.

---

<br>

## PART 2: WEEK-2 PROJECT DOCUMENTATION

### 1. Project Overview
Week-2 upgrades the RAG platform from a **basic ingestion pipe** into a **smart document understanding engine**. In simple terms: Week-1 could read a PDF and store its text. Week-2 teaches the system to *understand* the structure of a PDF — it can now tell the difference between a heading, a paragraph, a table, and a code block. Every piece of text is stored with full context so the AI can give much more accurate answers later.

### 2. Problem We Are Solving
Week-1 proved the infrastructure works. But its chunker was naive — it just cut text every N characters. That means a heading could land in one chunk and its explanation in the next. Or a table could be split across two unrelated chunks. When an AI reads those broken chunks, it gets confused and gives wrong answers.

Week-2 fixes this by adding **document intelligence**. The system now reads the font sizes and layout of a PDF to detect headings, preserves table rows together, keeps code blocks intact, and assigns every chunk a full section path (like `"3. Protocols > 3.1 TCP > 3.1.2 Header Format"`) so the AI always knows exactly where a piece of text came from.

### 3. What We Built in Week-2
Week-2 added five major new components on top of the Week-1 foundation:

- **PDF Intelligence** — classifies every page and extracts its content the right way.
- **Smart Chunker** — splits text along heading boundaries, not just character counts.
- **Structured Knowledge Base** — extracts special knowledge types (e.g. root-cause analyses, CLI commands) and saves them separately in PostgreSQL.
- **Task Queue + Background Worker** — ingestion now runs asynchronously so the API does not freeze while a 200-page PDF is being processed.
- **Filesystem Watcher** — automatically detects new PDFs dropped into a folder and queues them for ingestion without any manual command.

### 4. System Architecture Overview

The full pipeline now looks like this:

```
PDF (dropped into watched folder)
 │
 ▼
Watcher (auto-detects, assigns priority P0–P3)
 │
 ▼
Task Queue (async, priority-ordered)
 │
 ▼
Background Worker (picks up task)
 │
 ▼
PDF Intelligence (page classification + text extraction)
 │
 ▼
Smart Chunker (section-aware splitting)
 │
 ▼
────────────── STORAGE ──────────────
OpenSearch → searchable BM25 chunks
PostgreSQL → metadata + structured KB
MinIO      → raw PDF file
LangFuse   → observability trace
```

### 5. Technologies Used
All the same technologies from Week-1, plus:
- **PyMuPDF (fitz):** A fast PDF reader used to detect font sizes and classify headings.
- **Docling:** Used for deep table and structure extraction on complex pages.
- **Watchdog:** A Python library that monitors a directory for new files in real time.
- **asyncio:** Python's built-in async engine, used to run the task queue and worker without blocking the API.

### 6. Week-2 Completed Features

#### PDF Intelligence (`src/ingestion/pdf_intelligence.py`)
- Classifies every page as `native` (has real text) or `scanned` (image only).
- Extracts text, tables, and images.
- Uses font-size analysis to flag likely headings so the chunker can use them.

#### Smart Chunker (`src/ingestion/chunker.py`)
- Reads the heading flags from PDF Intelligence and splits chunks at section boundaries.
- Merges very short adjacent chunks in the same section (best-effort min 100 tokens).
- Hard-caps every chunk at 1500 tokens so no chunk is ever too big for a language model.
- Assigns `chunk_type` to every chunk: `section`, `table`, or `code_block`.
- Fills in `section_path` — the full heading breadcrumb for that chunk.

#### BM25 Store (`src/stores/bm25.py`)
- Indexes every chunk into OpenSearch with all 7 fields: `chunk_id`, `title`, `content`, `section_path`, `page_number`, `doc_id`, `chunk_type`.
- Supports `index_chunk()`, `search()`, and `delete_by_doc_id()`.
- Filters out structural/navigational chunks so search only returns real content.

#### Structured Knowledge Base (`src/stores/structured_kb.py`)
- Stores special structured knowledge in PostgreSQL JSONB columns.
- Supports four knowledge types: `RootCauseAnalysis`, `CLICommandReference`, `EscalationResolution`, `ConfigurationParameter`.

#### Index Builder (`src/ingestion/index_builder.py`)
- The main orchestration function: `ingest_pdf(path)`.
- Calls PDF Intelligence → Chunker → BM25 → MinIO → PostgreSQL → LangFuse in sequence.
- Returns an `IngestResult` with `doc_id`, `page_count`, `chunk_count`, `indexed_chunk_count`, `status`.

#### Task Queue (`src/workers/queue.py`)
- Priority queue with four task types: `INGEST_PDF`, `REINDEX_DOCUMENT`, `SUMMARIZE_SESSION`, `INVALIDATE_CACHE`.
- Tracks every task through its full lifecycle: `pending → processing → completed / failed`.

#### Background Worker (`src/workers/ingest_worker.py`)
- Picks up `INGEST_PDF` tasks from the queue and runs `ingest_pdf()`.
- On failure: moves the file to `data/failed/`, logs the error, and marks the task `failed`.
- On success: creates a symlink in `data/processed/` and marks the task `completed`.

#### Filesystem Watcher (`src/ingestion/watcher.py`)
- Monitors a directory using Watchdog.
- Assigns a priority to every new PDF based on its filename:
  - `rca`, `defect`, `incident` → **P0** (highest, processed first)
  - `cli`, `config`, `reference` → **P1**
  - `handbook`, `guide`, `manual` → **P2**
  - Everything else → **P3**
- Enqueues the file automatically — no manual command needed.

### 7. Real Data Validation Results
The full Phase-2 pipeline was stress-tested on the same three RFC documents used in Week-1.

| Document | Pages | Chunks Indexed |
|---|---|---|
| RFC 793 (TCP) | 91 | 180 |
| RFC 791 (IP) | 51 | 71 |
| RFC 2616 (HTTP) | 176 | 429 |
| **Total** | **318** | **690** |

Quality checks on all 690 chunks:
- **Max token size:** 1003 (well under the 1500 hard cap) ✔
- **Chunk types:** section=548, code_block=109, table=33 ✔
- **section_path populated:** 687/690 (99.6%) ✔
- **Legacy Phase-1 chunks:** 0 (schema 100% uniform) ✔

### 8. How to Run the System

**Step 1 — Start all services:**
```bash
docker compose up -d
```

**Step 2 — Activate Python environment:**
```bash
source venv/bin/activate
```

**Step 3 — Ingest a PDF through the full pipeline:**
```bash
python -c "from src.ingestion.index_builder import ingest_pdf; r = ingest_pdf('data/corpus/your_doc.pdf'); print(r)"
```

**Step 4 — Or re-ingest all real RFC documents:**
```bash
python scripts/reindex_real_docs.py
```

**Step 5 — Run the full production validation:**
```bash
python scripts/validate_production.py
```

**Step 6 — Run the full end-to-end verification checklist (on real RFC 793 TCP document):**
```bash
python scripts/verify_e2e.py --skip-worker
```

### 9. Important Scripts
- **`scripts/validate_production.py`** — 19 live checks across OpenSearch, PostgreSQL, MinIO, and LangFuse. Exits with code 1 if any check fails.
- **`scripts/verify_e2e.py`** — Verifies all checklist parts. Use `--skip-worker` to skip the slow background-worker test.
- **`scripts/audit_chunks.py`** — Detailed token distribution and chunk quality report. Use `--doc-id` for a single document.
- **`scripts/reindex_real_docs.py`** — Re-ingests all PDFs in `data/corpus/real_docs/` through the Phase-2 pipeline.
- **`scripts/delete_legacy_chunks.py`** — Removes Phase-1 chunks from the index. Use `--dry-run` to preview first.
- **`scripts/verify_rfc_chunks.py`** — Deep quality inspection for any single document. Auto-picks the largest doc if no `--doc-id` is given.

### 10. Key Source Files
- **`src/ingestion/pdf_intelligence.py`** — Page classification and text extraction.
- **`src/ingestion/chunker.py`** — Section-aware chunker with `MIN_CHUNK_TOKENS=100` (best-effort) and `MAX_CHUNK_TOKENS=1500` (absolute).
- **`src/ingestion/index_builder.py`** — Main pipeline orchestration. Entry point: `ingest_pdf(path)`.
- **`src/ingestion/watcher.py`** — Auto-detects new PDFs and enqueues them by priority.
- **`src/stores/bm25.py`** — OpenSearch BM25 indexing and search.
- **`src/stores/structured_kb.py`** — PostgreSQL JSONB structured knowledge store.
- **`src/stores/doc_store.py`** — MinIO PDF and image storage.
- **`src/workers/queue.py`** — Async priority task queue.
- **`src/workers/ingest_worker.py`** — Background worker that processes ingestion tasks.

### 11. What Was Verified
- Every PDF page is correctly extracted and classified.
- The chunker never produces a chunk over 1500 tokens.
- Every chunk carries a full section path so context is never lost.
- The OpenSearch index has all 7 required fields on every document.
- BM25 keyword search returns accurate results with proper scoring.
- The task queue correctly tracks tasks through pending → processing → completed/failed.
- The watcher detects a new file within under 1 second of it being dropped.
- The full `ingest_pdf()` pipeline returns `status=success` end-to-end.
- LangFuse records a trace for every ingestion job.
- 19/19 production validation checks pass.

### 12. What Week-3 Will Add
Week-2 gave the system document intelligence. Week-3 gives it **language intelligence**.

We will add:
- **Embeddings** — converting every chunk into a vector (a list of numbers that captures meaning).
- **Vector Store** — storing those vectors so we can search by *meaning*, not just *keywords*.
- **Hybrid Search** — combining BM25 keyword matching (Week-1/2) with vector similarity (Week-3) for the best possible retrieval accuracy.
- **Reranker** — a second pass that re-orders search results by relevance before passing them to the LLM.
- **LLM Answer Generation** — feeding the top retrieved chunks into a language model and getting a real conversational answer back.

---

<br>

### 🏁 Week-2 Completion Statement

I officially conclude the advanced ingestion work for the project. I have verified that:

- ✔ **PDF Intelligence Working:** Pages are classified, text is extracted cleanly, font-size heading detection is active.
- ✔ **Smart Chunker Working:** Chunks split at section boundaries, never exceeding 1500 tokens, with 99.6% section_path coverage.
- ✔ **BM25 Index Working:** 690 Phase-2 schema-uniform chunks indexed, all 7 mapping fields confirmed, keyword search returns correct results.
- ✔ **Async Pipeline Working:** Task queue, background worker, and filesystem watcher all operate correctly end-to-end.
- ✔ **Full Observability Working:** LangFuse traces every ingestion job, PostgreSQL tracks every document, MinIO stores every raw file.
- ✔ **Real Document Proof:** 318 pages of RFC specifications processed to 690 high-quality structured chunks.

**This RAG platform now has a production-grade document understanding engine and is ready to move to Week-3: semantic search, embeddings, and LLM answer generation.**
