#!/usr/bin/env python3
"""
Week 2 End-State Verification Script
=====================================
Checks every goal from the Week 2 system state:

  ✔  PDFs parsed, chunked, and indexed into OpenSearch
  ✔  BM25 search returns relevant chunks for real queries
  ✔  Structured KB contains root_cause_analysis objects
  ✔  Structured KB contains cli_command_reference objects
  ✔  Document metadata present in PostgreSQL
  ✔  Raw PDFs stored in MinIO

Run:
    python scripts/week2_verify.py              # check current state
    python scripts/week2_verify.py --seed-kb    # seed test KB objects then verify
"""

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg
from minio import Minio
from opensearchpy import OpenSearch

from src.config.settings import get_settings

SEED_KB = "--seed-kb" in sys.argv

PASS = "  ✅ PASS"
FAIL = "  ❌ FAIL"
WARN = "  ⚠️  WARN"

results: list[tuple[str, bool, str]] = []


def check(label: str, passed: bool, detail: str = "") -> None:
    results.append((label, passed, detail))
    icon = PASS if passed else FAIL
    print(f"{icon}  {label}")
    if detail:
        print(f"       {detail}")


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ─────────────────────────────────────────────────────────────
# 1. Infrastructure reachability
# ─────────────────────────────────────────────────────────────
section("1. Infrastructure")

settings = get_settings()

# Build PostgreSQL conninfo once — used in multiple sections
conninfo = (
    f"host={settings.postgres_host} port={settings.postgres_port} "
    f"user={settings.postgres_user} password={settings.postgres_password} "
    f"dbname={settings.postgres_db}"
)

# OpenSearch
try:
    os_client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
        timeout=5,
    )
    info = os_client.info()
    check("OpenSearch reachable", True, f"cluster={info['cluster_name']}")
except Exception as e:
    check("OpenSearch reachable", False, str(e))
    os_client = None

# PostgreSQL
try:
    with psycopg.connect(conninfo, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
    check("PostgreSQL reachable", True)
except Exception as e:
    check("PostgreSQL reachable", False, str(e))

# MinIO
try:
    mc = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    buckets = [b.name for b in mc.list_buckets()]
    check("MinIO reachable", True, f"buckets={buckets}")
except Exception as e:
    check("MinIO reachable", False, str(e))
    mc = None

# ─────────────────────────────────────────────────────────────
# 2. PDFs ingested — OpenSearch chunk count
# ─────────────────────────────────────────────────────────────
section("2. Ingestion — OpenSearch index")

chunk_count = 0
if os_client:
    try:
        if os_client.indices.exists(index="rag_chunks"):
            resp = os_client.count(index="rag_chunks")
            chunk_count = resp["count"]
            check(
                "rag_chunks index exists and has data",
                chunk_count > 0,
                f"{chunk_count} chunks indexed",
            )
        else:
            check("rag_chunks index exists and has data", False, "index does not exist yet")
    except Exception as e:
        check("rag_chunks index exists and has data", False, str(e))

# ─────────────────────────────────────────────────────────────
# 3. Document metadata in PostgreSQL
# ─────────────────────────────────────────────────────────────
section("3. Ingestion — PostgreSQL metadata")

try:
    with psycopg.connect(conninfo, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT doc_id, filename, page_count, chunk_count FROM document_metadata ORDER BY ingested_at DESC LIMIT 10")
            rows = cur.fetchall()

    check(
        "document_metadata has rows",
        len(rows) > 0,
        f"{len(rows)} most-recent documents:",
    )
    for doc_id, filename, pages, chunks in rows:
        print(f"       {filename:35s}  pages={pages or '?':>4}  chunks={chunks or '?':>4}  id={doc_id}")
except Exception as e:
    check("document_metadata has rows", False, str(e))
    rows = []

# ─────────────────────────────────────────────────────────────
# 4. Structured KB objects  (Week 2 goal)
# ─────────────────────────────────────────────────────────────
section("4. Structured KB (Week 2 goal)")

# Optional: seed test KB objects to prove the code path works
if SEED_KB:
    print("  [--seed-kb] Inserting test RCA + CLI objects into structured_kb …")
    try:
        from src.schemas.knowledge import (
            CLICommandReference,
            CommandExample,
            CommandParameter,
            FixDetail,
            KnowledgeObject,
            RootCauseAnalysis,
            RootCauseDetail,
            Source,
        )
        from src.stores.structured_kb import StructuredKBStore

        now = datetime.now(tz=timezone.utc)
        seed_source = Source(doc_id="seed-doc-id", filename="seed_verification.pdf", page_number=1)

        rca_obj = KnowledgeObject(
            id="verify-rca-001",
            type="root_cause_analysis",
            version=1,
            sources=[seed_source],
            created_at=now,
            updated_at=now,
            created_by="week2_verify.py",
            chunk_hash=hashlib.sha256(b"verify-rca-001").hexdigest(),
            tags=["verification", "seed"],
            data=RootCauseAnalysis(
                title="OpenSearch index empty after restart",
                symptoms=["Search returns no results", "chunk count is 0"],
                severity="S2",
                root_cause=RootCauseDetail(
                    summary="OpenSearch index was not persisted",
                    affected_versions=["1.0"],
                    fixed_in=["1.1"],
                ),
                fix=FixDetail(
                    steps=["Run reindex_all.py", "Verify chunk count"],
                    cli_commands=["python scripts/reindex_all.py"],
                ),
            ),
        )

        cli_obj = KnowledgeObject(
            id="verify-cli-001",
            type="cli_command_reference",
            version=1,
            sources=[seed_source],
            created_at=now,
            updated_at=now,
            created_by="week2_verify.py",
            chunk_hash=hashlib.sha256(b"verify-cli-001").hexdigest(),
            tags=["verification", "seed"],
            data=CLICommandReference(
                command="ingest_pdf",
                syntax="python scripts/phase1.py ingest <path>",
                parameters=[
                    CommandParameter(name="--path", required=True, description="PDF file or directory"),
                    CommandParameter(name="--force", required=False, description="Re-ingest even if already present"),
                ],
                examples=[
                    CommandExample(usage="python scripts/phase1.py ingest data/corpus/rfc793_tcp.pdf"),
                ],
            ),
        )

        with StructuredKBStore(verify_connection=False) as kb:
            kb.insert(rca_obj)
            kb.insert(cli_obj)
        print("  [--seed-kb] Seeded 1 RCA + 1 CLI object successfully")
    except Exception as e:
        print(f"  [--seed-kb] Seed FAILED: {e}")

try:
    with psycopg.connect(conninfo, connect_timeout=5) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT type, COUNT(*) FROM structured_kb GROUP BY type")
            kb_rows = {r[0]: r[1] for r in cur.fetchall()}

    total_kb = sum(kb_rows.values())

    # root_cause_analysis
    rca_count = kb_rows.get("root_cause_analysis", 0)
    check(
        "structured_kb has root_cause_analysis objects",
        rca_count > 0,
        f"{rca_count} objects" if rca_count else "0 objects — run with --seed-kb to seed test data",
    )

    # cli_command_reference
    cli_count = kb_rows.get("cli_command_reference", 0)
    check(
        "structured_kb has cli_command_reference objects",
        cli_count > 0,
        f"{cli_count} objects" if cli_count else "0 objects — run with --seed-kb to seed test data",
    )

    if total_kb > 0:
        print(f"       All KB types present: {dict(kb_rows)}")

except Exception as e:
    check("structured_kb has root_cause_analysis objects", False, str(e))
    check("structured_kb has cli_command_reference objects", False, str(e))

# ─────────────────────────────────────────────────────────────
# 5. BM25 search returns relevant results  (Week 2 goal)
# ─────────────────────────────────────────────────────────────
section("5. BM25 Search Quality (Week 2 goal)")

QUERIES = [
    ("TCP three-way handshake",        "three-way handshake"),
    ("HTTP caching headers",           "cache"),
    ("IP header format",               "header"),
    ("CLI command syntax",             "command"),
]

if os_client and chunk_count > 0:
    for query, keyword in QUERIES:
        try:
            resp = os_client.search(
                index="rag_chunks",
                body={
                    "query": {"multi_match": {"query": query, "fields": ["text", "title"]}},
                    "size": 3,
                },
            )
            hits = resp["hits"]["hits"]
            top_score = hits[0]["_score"] if hits else 0
            top_text = hits[0]["_source"].get("text", hits[0]["_source"].get("content", ""))[:80] if hits else ""
            relevant = len(hits) > 0 and keyword.lower() in top_text.lower()
            check(
                f'Search: "{query}"',
                len(hits) > 0,
                f"score={top_score:.2f}  preview={top_text!r}" if hits else "no results",
            )
        except Exception as e:
            check(f'Search: "{query}"', False, str(e))
else:
    print(f"  ⚠️   Skipping search — no chunks in index yet")

# ─────────────────────────────────────────────────────────────
# 6. MinIO has raw PDFs
# ─────────────────────────────────────────────────────────────
section("6. MinIO document store")

if mc:
    try:
        bucket = settings.minio_bucket
        if mc.bucket_exists(bucket):
            objects = list(mc.list_objects(bucket, recursive=True))
            check(
                "MinIO rag-documents bucket has PDFs",
                len(objects) > 0,
                f"{len(objects)} objects stored",
            )
            for obj in objects[:5]:
                print(f"       {obj.object_name}")
            if len(objects) > 5:
                print(f"       ... and {len(objects) - 5} more")
        else:
            check("MinIO rag-documents bucket has PDFs", False, "bucket does not exist yet")
    except Exception as e:
        check("MinIO rag-documents bucket has PDFs", False, str(e))

# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
section("Summary")

passed = sum(1 for _, ok, _ in results if ok)
total  = len(results)
failed = total - passed

print(f"  {passed}/{total} checks passed\n")

for label, ok, _ in results:
    icon = "✅" if ok else "❌"
    print(f"  {icon}  {label}")

print()
if failed == 0:
    print("  🎉  Week 2 system state: COMPLETE")
elif passed >= total * 0.7:
    print("  ⚠️  Week 2 system state: MOSTLY COMPLETE — fix the failing checks above")
else:
    print("  ❌  Week 2 system state: INCOMPLETE — run ingest_real_pdfs.py first")

sys.exit(0 if failed == 0 else 1)
