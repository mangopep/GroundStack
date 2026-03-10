#!/usr/bin/env python3
"""
Chunk Quality Audit
====================
Analyses the token-size distribution, chunk-type breakdown, and structural
quality of all indexed chunks in the rag_chunks OpenSearch index.

Reports:
  - Token size distribution in bands (0-10, 10-30, …, 1500+)
  - Per-document breakdown (doc_id, chunk count, min/max/avg tokens)
  - Smallest chunks with their section_path and content preview
  - Largest chunks (to confirm nothing exceeds 1500 tokens)
  - Chunk type distribution (section / table / code_block)
  - section_path population rate

Usage:
    python scripts/audit_chunks.py
    python scripts/audit_chunks.py --doc-id <doc_id>   # audit single doc
"""
import sys
import argparse
import logging
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.WARNING)

from opensearchpy import OpenSearch

parser = argparse.ArgumentParser(description="Chunk quality audit")
parser.add_argument("--doc-id", help="Audit a single document by doc_id")
parser.add_argument("--small-limit", type=int, default=5, help="Number of smallest chunks to show (default: 5)")
args = parser.parse_args()

client = OpenSearch([{"host": "localhost", "port": 9200}])

query: dict = {"match_all": {}}
if args.doc_id:
    query = {"term": {"doc_id": args.doc_id}}

resp = client.search(
    index="rag_chunks",
    body={
        "query": query,
        "size": 2000,
        "_source": ["content", "title", "section_path", "chunk_type", "is_structural", "doc_id"],
    },
)
total_in_index = resp["hits"]["total"]["value"]
chunks = [h["_source"] for h in resp["hits"]["hits"]]

print("=" * 60)
print("CHUNK QUALITY AUDIT")
if args.doc_id:
    print(f"doc_id: {args.doc_id}")
print(f"Chunks analysed: {len(chunks)} of {total_in_index} total in index")
print("=" * 60)

# ── Token size distribution ───────────────────────────────
content_chunks = [c for c in chunks if c.get("content") and not c.get("is_structural")]
word_sizes = [len(c["content"].split()) for c in content_chunks]

if not word_sizes:
    print("No content chunks found.")
    sys.exit(0)

mn, mx, avg = min(word_sizes), max(word_sizes), sum(word_sizes) / len(word_sizes)
over_1500 = sum(1 for s in word_sizes if s > 1500)
under_100 = sum(1 for s in word_sizes if s < 100)

print(f"\n[Token size — {len(word_sizes)} content chunks]")
print(f"  min={mn}  avg={avg:.0f}  max={mx}")
print(f"  Chunks > 1500 (must be 0):  {over_1500}  {'✓ PASS' if over_1500 == 0 else '✗ FAIL'}")
print(f"  Chunks < 100 (best-effort): {under_100} ({100 * under_100 / len(word_sizes):.1f}%)")

print("\n  Distribution:")
bands = [(0, 10), (10, 30), (30, 60), (60, 100), (100, 200), (200, 500), (500, 1000), (1000, 1500), (1500, 9999)]
for lo, hi in bands:
    count = sum(1 for s in word_sizes if lo <= s < hi)
    bar = "█" * (count // max(1, len(word_sizes) // 40))
    print(f"  {lo:5d}–{hi:5d}: {count:4d}  {bar}")

# ── Chunk type distribution ───────────────────────────────
print("\n[Chunk types]")
type_counts = Counter(c.get("chunk_type", "unknown") for c in chunks)
for t, n in sorted(type_counts.items()):
    print(f"  {t}: {n}")

# ── section_path coverage ─────────────────────────────────
has_path = sum(1 for c in chunks if c.get("section_path"))
pct = 100 * has_path / len(chunks) if chunks else 0
print(f"\n[section_path coverage]")
print(f"  {has_path}/{len(chunks)} chunks have section_path ({pct:.1f}%)")

# ── Per-document breakdown ────────────────────────────────────────────────
if not args.doc_id:
    print("\n[Per-document breakdown]")
    by_doc: dict[str, list] = {}
    for c in content_chunks:
        by_doc.setdefault(c.get("doc_id", "unknown"), []).append(len(c["content"].split()))
    for doc_id, sizes in sorted(by_doc.items(), key=lambda x: -len(x[1])):
        print(
            f"  {doc_id[:20]}  chunks={len(sizes):4d}  "
            f"min={min(sizes):4d}  avg={sum(sizes)//len(sizes):4d}  max={max(sizes):4d}"
        )

# ── Smallest chunks ───────────────────────────────────────
print(f"\n[Smallest {args.small_limit} section chunks]")
section_chunks = sorted(
    [c for c in content_chunks if c.get("chunk_type") == "section"],
    key=lambda c: len(c["content"].split()),
)
for c in section_chunks[: args.small_limit]:
    toks = len(c["content"].split())
    print(f"  section_path={c.get('section_path')!r}  tokens={toks}")
    print(f"  content: {c['content'][:120]!r}")
    print()

# ── Largest chunks ────────────────────────────────────────
print(f"[Largest 3 chunks]")
for c in sorted(content_chunks, key=lambda c: len(c["content"].split()), reverse=True)[:3]:
    toks = len(c["content"].split())
    print(f"  section_path={c.get('section_path')!r}  chunk_type={c.get('chunk_type')}  tokens={toks}")

print("\n" + "=" * 60)
print(f"Max-size constraint (≤1500): {'PASS' if over_1500 == 0 else 'FAIL'}")
print(f"Min-size best-effort (≥100): {under_100} chunks under threshold ({100 * under_100 / len(word_sizes):.1f}%)")
