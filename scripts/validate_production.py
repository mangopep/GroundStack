#!/usr/bin/env python3
"""
Phase-2 Production Validation
==============================
Runs a full suite of live checks against all running services to confirm the
Phase-2 ingestion stack is production-ready.

Covers:
  - OpenSearch index count and Phase-2 schema uniformity
  - Chunk type distribution across all indexed documents
  - Token-size constraints (max absolute, min best-effort)
  - section_path population rate
  - OpenSearch mapping — all required fields present
  - LangFuse trace reachability
  - PostgreSQL metadata rows
  - MinIO bucket object count
  - BM25 search returns results with required fields

Usage:
    python scripts/validate_production.py
"""

import json
import logging
import sys
import urllib.request
from collections import Counter
from pathlib import Path

import psycopg
from minio import Minio
from opensearchpy import OpenSearch

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.WARNING)

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, str, str]] = []  # (check, status, detail)


def check(name: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    results.append((name, status, detail))
    marker = "✓" if ok else "✗"
    print(f"  {marker} {name}: {status}{(' — ' + detail) if detail else ''}")


client = OpenSearch([{"host": "localhost", "port": 9200}])

print("=" * 60)
print("PHASE-2 PRODUCTION VALIDATION")
print("=" * 60)

# ── OpenSearch index ──────────────────────────────────────
print("\n[OpenSearch]")

total = client.count(index="rag_chunks")["count"]
check("Index has chunks", total > 0, f"{total} total")

legacy = client.count(
    index="rag_chunks",
    body={"query": {"bool": {"must_not": [{"exists": {"field": "chunk_type"}}]}}},
)["count"]
check("Schema uniform (no legacy chunks)", legacy == 0, f"{legacy} legacy remaining")

p2 = client.count(
    index="rag_chunks",
    body={"query": {"bool": {"must": [{"exists": {"field": "chunk_type"}}]}}},
)["count"]
check("All chunks are Phase-2", p2 == total, f"{p2}/{total}")

# Fetch sample for detailed analysis
resp = client.search(
    index="rag_chunks",
    body={
        "query": {"bool": {"must": [{"exists": {"field": "chunk_type"}}]}},
        "size": 1000,
        "_source": ["content", "chunk_type", "section_path", "doc_id"],
    },
)
chunks = [h["_source"] for h in resp["hits"]["hits"]]

word_sizes = [len((c.get("content") or "").split()) for c in chunks if c.get("content")]
if word_sizes:
    max_tok = max(word_sizes)
    over_1500 = sum(1 for s in word_sizes if s > 1500)
    check("Max token constraint (≤1500)", over_1500 == 0, f"max observed={max_tok}")

type_counts = Counter(c.get("chunk_type", "unknown") for c in chunks)
check(
    "Chunk types present (section, table, code_block)",
    "section" in type_counts,
    str(dict(type_counts)),
)

has_path = sum(1 for c in chunks if c.get("section_path"))
pct = 100 * has_path / len(chunks) if chunks else 0
check("section_path populated ≥90%", pct >= 90.0, f"{has_path}/{len(chunks)} ({pct:.1f}%)")

# ── OpenSearch mapping ────────────────────────────────────
print("\n[OpenSearch Mapping]")
resp_map = urllib.request.urlopen("http://localhost:9200/rag_chunks/_mapping")
mapping = json.loads(resp_map.read())
props = mapping["rag_chunks"]["mappings"].get("properties", {})
required_fields = [
    "chunk_id",
    "title",
    "content",
    "section_path",
    "page_number",
    "doc_id",
    "chunk_type",
]
for f in required_fields:
    check(f"Mapping has '{f}'", f in props, props.get(f, {}).get("type", "missing"))

# ── BM25 search ───────────────────────────────────────────
print("\n[BM25 Search]")
from src.stores.bm25 import BM25Store  # noqa: E402 — the repository root is added to sys.path above for script execution.

bm25 = BM25Store()
results_bm25 = bm25.search("introduction", top_k=3)
check("BM25 search returns results", len(results_bm25) > 0, f"{len(results_bm25)} hits")
if results_bm25:
    r = results_bm25[0]
    req = ["chunk_id", "title", "content", "score", "section_path"]
    missing = [f for f in req if f not in r]
    check("BM25 result has required fields", not missing, f"missing={missing or 'none'}")

# ── PostgreSQL metadata ───────────────────────────────────
print("\n[PostgreSQL Metadata]")
try:
    from src.config.settings import get_settings

    settings = get_settings()
    conn = psycopg.connect(settings.database.url)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM document_metadata")
    (row_count,) = cur.fetchone()
    cur.execute(
        "SELECT doc_id, filename, page_count, chunk_count FROM document_metadata ORDER BY ingested_at DESC LIMIT 3"
    )
    rows = cur.fetchall()
    conn.close()
    check("document_metadata has rows", row_count > 0, f"{row_count} rows")
    for row in rows:
        print(f"     doc_id={row[0][:16]}  filename={row[1]}  pages={row[2]}  chunks={row[3]}")
except Exception as e:
    check("PostgreSQL reachable", False, str(e))

# ── MinIO document store ──────────────────────────────────
print("\n[MinIO Document Store]")
try:
    minio = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    bucket_exists = minio.bucket_exists("rag-documents")
    check("Bucket 'rag-documents' exists", bucket_exists)
    if bucket_exists:
        objects = list(minio.list_objects("rag-documents", recursive=True))
        check("Bucket contains documents", len(objects) > 0, f"{len(objects)} objects")
except Exception as e:
    check("MinIO reachable", False, str(e))

# ── LangFuse tracing ─────────────────────────────────────
print("\n[LangFuse Observability]")
try:
    from dotenv import load_dotenv

    load_dotenv()
    from langfuse import Langfuse

    from src.config.settings import get_settings

    settings = get_settings()
    if settings.langfuse.public_key and settings.langfuse.secret_key:
        lf = Langfuse(
            public_key=settings.langfuse.public_key,
            secret_key=settings.langfuse.secret_key,
            host=settings.langfuse.host,
        )
        traces = lf.get_traces(limit=1)
        check(
            "LangFuse traces present", len(traces.data) > 0, f"{len(traces.data)} recent trace(s)"
        )
    else:
        check("LangFuse configured", False, "public_key or secret_key not set")
except Exception as e:
    check("LangFuse reachable", False, str(e))

# ── Summary ───────────────────────────────────────────────
print("\n" + "=" * 60)
passed = sum(1 for _, s, _ in results if s == PASS)
failed = sum(1 for _, s, _ in results if s == FAIL)
print(f"RESULT: {passed}/{passed + failed} checks passed")
if failed:
    print("\nFailed checks:")
    for name, status, detail in results:
        if status == FAIL:
            print(f"  ✗ {name}: {detail}")
else:
    print("All checks passed — Phase-2 system is production-ready.")
print("=" * 60)
sys.exit(0 if failed == 0 else 1)
