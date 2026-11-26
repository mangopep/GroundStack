#!/usr/bin/env python3
"""
Test Search Quality
===================
This script queries your populated OpenSearch index to prove that the
real documents (like the TCP, HTTP, and IP RFCs) are successfully searchable.
"""

import sys
from pathlib import Path

from opensearchpy import OpenSearch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config.settings import get_settings


def test_search():
    print("=" * 80)
    print("🔍 Testing Search Quality on Ingested Data")
    print("=" * 80)

    settings = get_settings()

    # Connect to OpenSearch
    os_client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
    )

    # Some test questions based on the real RFC PDFs
    test_queries = [
        "What is the three-way handshake in TCP?",
        "How does HTTP caching work?",
        "What is the Internet Protocol (IP) header format?",
    ]

    for question in test_queries:
        print(f"\n❓ Query: '{question}'")
        print("-" * 60)

        # Simple BM25 match query since we haven't built the Vector Embedder yet in Week 1
        query_body = {"query": {"match": {"text": question}}, "highlight": {"fields": {"text": {}}}}

        try:
            response = os_client.search(index=settings.opensearch_index, body=query_body, size=2)

            hits = response["hits"]["hits"]
            if not hits:
                print("   ❌ No results found!")
                continue

            for i, hit in enumerate(hits, 1):
                score = hit["_score"]
                source = hit["_source"]
                filename = source.get("filename", "Unknown")

                # Get the highlight if available, else snippet the text
                highlights = hit.get("highlight", {}).get("text", [])
                if highlights:
                    snippet = highlights[0].replace("\n", " ").strip()
                else:
                    snippet = source["text"][:150].replace("\n", " ") + "..."

                print(f"   [{i}] Score: {score:.2f} | 📄 Source: {filename}")
                print(f'       Snippet: "{snippet}"\n')

        except Exception as e:
            print(f"   ❌ Search failed: {e}")


if __name__ == "__main__":
    test_search()
