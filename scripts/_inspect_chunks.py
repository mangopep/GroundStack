#!/usr/bin/env python3
"""Quick chunk inspector."""

import sys

sys.path.insert(0, ".")

from opensearchpy import OpenSearch

from src.config.settings import get_settings

s = get_settings()
oc = OpenSearch(
    hosts=[{"host": s.opensearch_host, "port": s.opensearch_port}],
    use_ssl=False,
    verify_certs=False,
)

filename = sys.argv[1] if len(sys.argv) > 1 else None

if filename:
    query = {"bool": {"should": [{"term": {"filename": filename}}, {"term": {"doc_id": filename}}]}}
else:
    query = {"match_all": {}}

r = oc.search(
    index="rag_chunks",
    body={"query": query, "size": 10, "sort": [{"ingested_at": {"order": "desc"}}]},
)
hits = r["hits"]["hits"]
print(f"total={r['hits']['total']['value']}  showing {len(hits)}")
for h in hits:
    src = h["_source"]
    ctype = src.get("chunk_type", "N/A")
    text = src.get("text", "")[:120]
    fname = src.get("filename", "?")
    print(f"  {fname}  type={ctype!r}  text={text!r}")
