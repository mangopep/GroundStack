#!/usr/bin/env python3
"""
Delete Legacy Phase-1 Chunks
==============================
Removes all chunks from the rag_chunks OpenSearch index that were indexed by
the Phase-1 pipeline (i.e. chunks missing the `chunk_type` field introduced
in Phase 2).

Use --dry-run to preview the count that would be deleted without making any
changes to the index.

Usage:
    python scripts/delete_legacy_chunks.py            # actually delete
    python scripts/delete_legacy_chunks.py --dry-run  # preview only
"""
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
logging.basicConfig(level=logging.WARNING)

parser = argparse.ArgumentParser(description="Delete legacy Phase-1 chunks from the index")
parser.add_argument("--dry-run", action="store_true", help="Count but do not delete")
args = parser.parse_args()

from opensearchpy import OpenSearch

client = OpenSearch([{"host": "localhost", "port": 9200}])

LEGACY_QUERY = {
    "query": {
        "bool": {
            "must_not": [{"exists": {"field": "chunk_type"}}]
        }
    }
}

# Count legacy chunks first
count_resp = client.count(index="rag_chunks", body=LEGACY_QUERY)
legacy_count = count_resp["count"]
total_resp = client.count(index="rag_chunks")
total_count = total_resp["count"]

print(f"Total chunks in index:   {total_count}")
print(f"Legacy (no chunk_type):  {legacy_count}")

if legacy_count == 0:
    print("Nothing to delete — index is already schema-uniform.")
    sys.exit(0)

if args.dry_run:
    print(f"\n[dry-run] Would delete {legacy_count} legacy chunks. Re-run without --dry-run to proceed.")
    sys.exit(0)

print(f"\nDeleting {legacy_count} legacy Phase-1 chunks ...")
result = client.delete_by_query(index="rag_chunks", body=LEGACY_QUERY, params={"refresh": "true"})
deleted = result.get("deleted", 0)

# Verify
check_resp = client.count(index="rag_chunks", body=LEGACY_QUERY)
remaining_legacy = check_resp["count"]
new_total = client.count(index="rag_chunks")["count"]

print(f"Deleted:   {deleted}")
print(f"Remaining: {new_total} chunks ({remaining_legacy} legacy)")
if remaining_legacy == 0:
    print("Schema uniformity: PASS — all chunks now have chunk_type")
else:
    print(f"Schema uniformity: FAIL — {remaining_legacy} legacy chunks still present")
    sys.exit(1)
