#!/usr/bin/env python3
"""
Re-ingest Real Corpus Documents
=================================
Runs the Phase-2 ingestion pipeline on real PDF documents in the corpus.
By default processes all PDFs under `data/corpus/real_docs/`.  Pass explicit
paths as positional arguments to target specific files.

Each document is processed through the full pipeline:
  PDF → page extraction → chunking → OpenSearch indexing → PostgreSQL metadata → MinIO upload

Usage:
    python scripts/reindex_real_docs.py                               # all real docs
    python scripts/reindex_real_docs.py data/corpus/real_docs/rfc793_tcp.pdf
    python scripts/reindex_real_docs.py data/corpus/real_docs/rfc791_ip.pdf data/corpus/real_docs/rfc2616_http.pdf
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.WARNING)

parser = argparse.ArgumentParser(description="Re-ingest real corpus PDF documents via Phase-2 pipeline")
parser.add_argument("paths", nargs="*", help="PDF paths to ingest (default: data/corpus/real_docs/*.pdf)")
args = parser.parse_args()

if args.paths:
    pdf_paths = [Path(p) for p in args.paths]
else:
    real_docs_dir = Path("data/corpus/real_docs")
    if not real_docs_dir.exists():
        print(f"ERROR: {real_docs_dir} does not exist. Pass explicit paths or create the directory.")
        sys.exit(1)
    pdf_paths = sorted(real_docs_dir.glob("*.pdf"))
    if not pdf_paths:
        print(f"No PDF files found in {real_docs_dir}")
        sys.exit(1)

print(f"Documents to ingest: {len(pdf_paths)}")
for p in pdf_paths:
    print(f"  {p}")
print()

from src.ingestion.index_builder import ingest_pdf

total_pages = 0
total_chunks = 0
total_indexed = 0
failures: list[str] = []

for pdf_path in pdf_paths:
    path = Path(pdf_path)
    if not path.exists():
        print(f"[SKIP] {path} — file not found")
        failures.append(str(path))
        continue

    print(f"Ingesting {path.name} ...", flush=True)
    try:
        result = ingest_pdf(str(path))
        status_icon = "✓" if result.status == "success" else "✗"
        print(
            f"  {status_icon} status={result.status}  "
            f"pages={result.page_count}  "
            f"chunks={result.chunk_count}  "
            f"indexed={result.indexed_chunk_count}"
        )
        if result.status == "success":
            total_pages += result.page_count
            total_chunks += result.chunk_count
            total_indexed += result.indexed_chunk_count
        else:
            err = getattr(result, "error", None)
            if err:
                print(f"  error: {err}")
            failures.append(path.name)
    except Exception as e:
        print(f"  ✗ EXCEPTION: {e}")
        failures.append(path.name)

print()
print("=" * 50)
print(f"Ingested: {len(pdf_paths) - len(failures)}/{len(pdf_paths)} documents")
print(f"Total: pages={total_pages}  chunks={total_chunks}  indexed={total_indexed}")
if failures:
    print(f"Failed: {', '.join(failures)}")
    sys.exit(1)
