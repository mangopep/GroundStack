#!/usr/bin/env python3
"""
RFC / Large-Document Chunk Quality Inspector
=============================================
Deep-dives into chunk quality for a single document in the index — showing
token statistics, chunk-type distribution, section_path samples, and an
example content preview from the largest section chunk.

By default selects the document with the most indexed chunks (usually the
largest real doc).  Pass --doc-id to inspect a specific document.

Usage:
    python scripts/verify_rfc_chunks.py                          # inspect largest doc
    python scripts/verify_rfc_chunks.py --doc-id rfc793_tcp.pdf  # specific doc
    python scripts/verify_rfc_chunks.py --size 500               # fetch up to 500 chunks
"""
import sys
import argparse
import logging
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.WARNING)

parser = argparse.ArgumentParser(description="Deep chunk quality inspection for a single document")
parser.add_argument("--doc-id", help="doc_id to inspect (default: document with most chunks)")
parser.add_argument("--size", type=int, default=500, help="Max chunks to fetch (default: 500)")
args = parser.parse_args()

from opensearchpy import OpenSearch

client = OpenSearch([{"host": "localhost", "port": 9200}])

# ── Resolve doc_id ────────────────────────────────────────
if args.doc_id:
    doc_id = args.doc_id
else:
    agg_resp = client.search(
        index="rag_chunks",
        body={
            "query": {"bool": {"must": [{"exists": {"field": "chunk_type"}}]}},
            "size": 0,
            "aggs": {"by_doc": {"terms": {"field": "doc_id", "size": 50}}},
        },
    )
    buckets = agg_resp["aggregations"]["by_doc"]["buckets"]
    if not buckets:
        print("No Phase-2 documents found in index.")
        sys.exit(1)
    largest = max(buckets, key=lambda b: b["doc_count"])
    doc_id = largest["key"]
    print(f"(auto-selected largest doc: {doc_id} — {largest['doc_count']} chunks)")

# ── Fetch chunks ──────────────────────────────────────────
resp = client.search(
    index="rag_chunks",
    body={
        "query": {"term": {"doc_id": doc_id}},
        "size": args.size,
        "_source": ["content", "title", "section_path", "page_number", "chunk_type", "is_structural", "doc_id"],
    },
)
total_in_index = resp["hits"]["total"]["value"]
chunks = [h["_source"] for h in resp["hits"]["hits"]]

print("=" * 60)
print(f"Chunk Quality Report — doc_id={doc_id!r}")
print(f"Chunks fetched: {len(chunks)} of {total_in_index} in index")
print("=" * 60)

# ── Token stats ───────────────────────────────────────────
content_chunks = [c for c in chunks if c.get("content") and not c.get("is_structural")]
if not content_chunks:
    print("No content chunks found for this document.")
    sys.exit(0)

word_sizes = [len(c["content"].split()) for c in content_chunks]
mn, mx, avg = min(word_sizes), max(word_sizes), sum(word_sizes) / len(word_sizes)
under_100 = sum(1 for s in word_sizes if s < 100)
over_1500 = sum(1 for s in word_sizes if s > 1500)

print(f"\n[Token sizes — {len(word_sizes)} content chunks]")
print(f"  min={mn}  avg={avg:.0f}  max={mx}")
print(f"  Chunks > 1500 (must be 0):  {over_1500}  {'✓ PASS' if over_1500 == 0 else '✗ FAIL'}")
print(f"  Chunks < 100 (best-effort): {under_100} ({100 * under_100 / len(word_sizes):.1f}%)")

# Token distribution
print("\n  Distribution:")
bands = [(0, 10), (10, 30), (30, 60), (60, 100), (100, 200), (200, 500), (500, 1000), (1000, 1500), (1500, 9999)]
for lo, hi in bands:
    count = sum(1 for s in word_sizes if lo <= s < hi)
    if count:
        bar = "█" * (count // max(1, len(word_sizes) // 40))
        print(f"  {lo:5d}–{hi:5d}: {count:4d}  {bar}")

# ── Chunk type distribution ───────────────────────────────
print(f"\n[Chunk types]")
type_counts = Counter(c.get("chunk_type", "unknown") for c in chunks)
for t, n in sorted(type_counts.items()):
    print(f"  {t}: {n}")

# ── section_path coverage ─────────────────────────────────
has_path = sum(1 for c in chunks if c.get("section_path"))
pct = 100 * has_path / len(chunks)
print(f"\n[section_path coverage]")
print(f"  {has_path}/{len(chunks)} chunks ({pct:.1f}%)")
sample_paths = sorted({c["section_path"] for c in chunks if c.get("section_path")})[:10]
print("  Sample section_paths:")
for p in sample_paths:
    print(f"    {p!r}")

# ── Sample large section chunk ────────────────────────────
print("\n[Sample section chunk (largest)]")
section_chunks = [c for c in content_chunks if c.get("chunk_type") == "section"]
if section_chunks:
    big = max(section_chunks, key=lambda c: len(c["content"].split()))
    print(f"  title:        {big.get('title')!r}")
    print(f"  section_path: {big.get('section_path')!r}")
    print(f"  page_number:  {big.get('page_number')}")
    print(f"  tokens:       {len(big['content'].split())}")
    print(f"  content[:300]:\n    {big['content'][:300]!r}")

# ── Verdict ───────────────────────────────────────────────
print("\n" + "=" * 60)
print(f"Max-size constraint (≤1500): {'PASS' if over_1500 == 0 else 'FAIL'}")
print(f"section_path coverage: {pct:.1f}%  {'✓' if pct >= 90 else '⚠ below 90%'}")
