#!/usr/bin/env python3
"""
End-to-End Phase-2 Pipeline Verification
==========================================
Runs all Phase2.md checklist items (Parts 2-11) against live services.
Designed to be run after `docker compose up -d` to confirm the platform is
fully operational.

Tests:
  Part 2  — PDF Intelligence  (process_pdf → PageResult)
  Part 3  — Chunker           (chunk_pages → ChunkResult schema + token bounds)
  Part 4  — BM25 Search       (OpenSearch query returns results with expected fields)
  Part 5  — Structured KB     (StructuredKBStore.search_by_type executes without error)
  Part 6  — Document Store    (MinIO bucket exists and contains objects)
  Part 7  — Metadata          (PostgreSQL document_metadata has rows)
  Part 8  — Ingestion Watcher (classify_priority + live file-detection test)
  Part 9  — Task Queue        (get_status returns all 4 required keys)
  Part 10 — Background Worker (handler registered, task processed to terminal state)
  Part 11 — Full E2E Pipeline (ingest_pdf returns status=success with non-zero counts)

Usage:
    python scripts/verify_e2e.py
    python scripts/verify_e2e.py --pdf data/corpus/01_handbook.pdf
    python scripts/verify_e2e.py --skip-worker  # skip the slow Part 10 worker test
"""
import sys
import asyncio
import argparse
import logging
import time
import shutil
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.WARNING)

parser = argparse.ArgumentParser(description="End-to-end Phase-2 verification")
parser.add_argument("--pdf", default="data/corpus/real_docs/rfc793_tcp.pdf", help="Test PDF path")
parser.add_argument("--skip-worker", action="store_true", help="Skip the slow background-worker test (Part 10)")
args = parser.parse_args()

passed: list[str] = []
failed: list[str] = []


def check(part: str, ok: bool, detail: str = "") -> bool:
    status = "✓ PASS" if ok else "✗ FAIL"
    msg = f"  {status}  {part}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    (passed if ok else failed).append(part)
    return ok


print("=" * 60)
print("Phase-2 End-to-End Verification")
print(f"Test PDF: {args.pdf}")
print("=" * 60)

# ── Part 2: PDF Intelligence ──────────────────────────────
print("\n[Part 2] PDF Intelligence")
try:
    from src.ingestion.pdf_intelligence import process_pdf
    pages = process_pdf(args.pdf)
    p0 = pages[0] if pages else None
    ok_count = len(pages) > 0
    ok_fields = p0 is not None and all(
        hasattr(p0, f) for f in ("page_num", "text", "page_type", "extraction_status")
    )
    ok_text = p0 is not None and bool(p0.text.strip())
    check("Part 2", ok_count and ok_fields and ok_text,
          f"{len(pages)} pages extracted, text present={ok_text}")
except Exception as e:
    check("Part 2", False, str(e))
    pages = []

# ── Part 3: Chunker ───────────────────────────────────────
print("\n[Part 3] Chunker")
try:
    from src.ingestion.chunker import chunk_pages
    chunks = chunk_pages(pages, doc_id="verify_e2e_test")
    required = ["id", "title", "content", "section_path", "page_numbers", "chunk_type"]
    if chunks:
        c0 = chunks[0]
        missing = [f for f in required if not hasattr(c0, f)]
        sizes = [len((getattr(c, "content", "") or "").split()) for c in chunks]
        over_1500 = sum(1 for s in sizes if s > 1500)
        ok = (not missing) and (over_1500 == 0)
        check("Part 3", ok,
              f"{len(chunks)} chunks, max_tokens={max(sizes)}, over_1500={over_1500}, missing_fields={missing or 'none'}")
    else:
        check("Part 3", False, "no chunks produced")
except Exception as e:
    check("Part 3", False, str(e))

# ── Part 4: BM25 Search ───────────────────────────────────
print("\n[Part 4] BM25 Search")
try:
    from src.stores.bm25 import BM25Store
    import urllib.request, json
    store = BM25Store()
    # Use a term present in the RFC corpus; "protocol" appears in all three RFCs
    results = store.search("protocol", top_k=3)
    req_fields = ["chunk_id", "title", "content", "score", "section_path"]
    idx_resp = urllib.request.urlopen("http://localhost:9200/rag_chunks/_count")
    index_count = json.loads(idx_resp.read()).get("count", 0)
    if results:
        missing = [f for f in req_fields if f not in results[0]]
        check("Part 4", len(results) > 0 and not missing and index_count > 0,
              f"results={len(results)}, index_count={index_count}, missing_fields={missing or 'none'}")
    else:
        check("Part 4", False, f"no results returned (index has {index_count} docs)")
except Exception as e:
    check("Part 4", False, str(e))

# ── Part 5: Structured KB ─────────────────────────────────
print("\n[Part 5] Structured KB")
try:
    from src.stores.structured_kb import StructuredKBStore
    kb = StructuredKBStore()
    results5 = kb.search_by_type("root_cause_analysis", "error")
    check("Part 5", True, f"store functional, returned {len(results5)} items (0 ok if no RCA data)")
except Exception as e:
    check("Part 5", False, str(e))

# ── Part 6: Document Store (MinIO) ────────────────────────
print("\n[Part 6] Document Store (MinIO)")
try:
    from minio import Minio
    mc = Minio("localhost:9000", access_key="minioadmin", secret_key="minioadmin", secure=False)
    BUCKET = "rag-documents"
    found = mc.bucket_exists(BUCKET)
    if found:
        objects = list(mc.list_objects(BUCKET, recursive=True))
        check("Part 6", len(objects) > 0, f"bucket='{BUCKET}', objects={len(objects)}")
    else:
        check("Part 6", False, f"bucket '{BUCKET}' does not exist")
except Exception as e:
    check("Part 6", False, str(e))

# ── Part 7: Metadata Persistence ─────────────────────────
print("\n[Part 7] Metadata Persistence (PostgreSQL)")
try:
    import psycopg
    conn = psycopg.connect("host=localhost port=5432 dbname=rag_platform user=rag password=rag_dev_2026")
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM document_metadata")
    row_count = cur.fetchone()[0]
    conn.close()
    check("Part 7", row_count > 0, f"document_metadata rows={row_count}")
except Exception as e:
    check("Part 7", False, str(e))

# ── Part 8: Ingestion Watcher ─────────────────────────────
print("\n[Part 8] Ingestion Watcher")
try:
    from src.ingestion.watcher import classify_priority, IngestionWatcher
    priority_tests = [
        ("rca_analysis.pdf", "P0", 0),
        ("cli_reference.pdf", "P1", 1),
        ("handbook_v2.pdf", "P2", 2),
        ("release_notes.pdf", "P3", 3),
    ]
    priority_ok = all(
        classify_priority(Path(fname)) == (label, num)
        for fname, label, num in priority_tests
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        watcher = IngestionWatcher(watch_path=tmpdir, max_workers=1, debounce_seconds=0.2)
        watcher.start()
        time.sleep(0.3)
        shutil.copy2(args.pdf, Path(tmpdir) / "test_watch.pdf")
        time.sleep(0.8)
        job_detected = watcher._job_counter > 0
        watcher.stop()
    check("Part 8", priority_ok and job_detected,
          f"classify_priority ok={priority_ok}, job_detected={job_detected}")
except Exception as e:
    check("Part 8", False, str(e))

# ── Part 9: Task Queue ────────────────────────────────────
print("\n[Part 9] Task Queue")
try:
    from src.workers.queue import get_queue

    async def _check_queue():
        q = get_queue()
        status = q.get_status()
        required_keys = ["pending", "processing", "completed", "failed"]
        missing = [k for k in required_keys if k not in status]
        return not missing, status, missing

    ok9, q_status, missing_keys = asyncio.run(_check_queue())
    check("Part 9", ok9, f"status={q_status}, missing={missing_keys or 'none'}")
except Exception as e:
    check("Part 9", False, str(e))

# ── Part 10: Background Worker ────────────────────────────
print("\n[Part 10] Background Worker")
if args.skip_worker:
    print("  (skipped — --skip-worker flag set)")
else:
    try:
        from src.workers.queue import TaskQueue, TaskType
        from src.workers.ingest_worker import IngestWorker

        async def _test_worker():
            q = TaskQueue(max_workers=1)
            worker = IngestWorker(queue=q)
            worker.register()
            has_handler = TaskType.INGEST_PDF in q._handlers
            task_id = await q.enqueue(
                task_type=TaskType.INGEST_PDF,
                payload={"pdf_path": args.pdf},
                priority=2,
            )
            worker_task = asyncio.create_task(worker.run_forever())
            for _ in range(90):  # up to 3 min
                await asyncio.sleep(2)
                info = q.get_task(task_id)
                if info and info.get("status") in ("completed", "failed"):
                    break
            final = q.get_task(task_id)
            final_status = final.get("status") if final else "unknown"
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
            return has_handler, task_id, final_status

        has_handler, task_id, final_status = asyncio.run(_test_worker())
        ok10 = has_handler and task_id is not None and final_status in ("completed", "failed")
        check("Part 10", ok10, f"handler_registered={has_handler}, task_id={task_id}, final_status={final_status}")
    except Exception as e:
        check("Part 10", False, str(e))

# ── Part 11: Full E2E Pipeline ────────────────────────────
print("\n[Part 11] Full E2E Pipeline (ingest_pdf)")
try:
    from src.ingestion.index_builder import ingest_pdf
    result = ingest_pdf(args.pdf)
    ok11 = (
        result.status == "success"
        and result.page_count > 0
        and result.chunk_count > 0
        and result.indexed_chunk_count > 0
    )
    check("Part 11", ok11,
          f"status={result.status}, pages={result.page_count}, chunks={result.chunk_count}, indexed={result.indexed_chunk_count}")
except Exception as e:
    check("Part 11", False, str(e))

# ── Summary ───────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"PASSED: {len(passed)}/{len(passed) + len(failed)}")
if failed:
    print(f"FAILED: {', '.join(failed)}")
print("=" * 60)
sys.exit(0 if not failed else 1)
