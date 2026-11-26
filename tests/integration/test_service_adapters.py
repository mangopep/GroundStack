"""Smoke-test real OpenSearch and Redis adapters using unique test data."""

import os
import uuid

import pytest
from redis import Redis

from src.stores.bm25 import BM25Store

pytestmark = pytest.mark.skipif(
    os.environ.get("GROUNDSTACK_RUN_SERVICE_INTEGRATION") != "1",
    reason="Set GROUNDSTACK_RUN_SERVICE_INTEGRATION=1 with disposable services",
)


def test_bm25_round_trip_against_opensearch() -> None:
    marker = f"groundstackmarker{uuid.uuid4().hex}"
    index = f"groundstack-ci-{uuid.uuid4().hex}"
    store = BM25Store(index_name=index)
    store._client.indices.create(index=index)
    try:
        store.index_chunk(
            {
                "id": f"chunk-{uuid.uuid4().hex}",
                "doc_id": f"doc-{uuid.uuid4().hex}",
                "title": "Isolated CI integration fixture",
                "content": f"Unique searchable term {marker}",
            }
        )

        results = store.search(marker, top_k=5)
        assert results
        assert marker in results[0]["content"]
    finally:
        store._client.indices.delete(index=index, ignore=[404])


def test_redis_round_trip_uses_a_unique_key() -> None:
    client = Redis(
        host=os.environ.get("REDIS_HOST", "127.0.0.1"),
        port=int(os.environ.get("REDIS_PORT", "16379")),
        socket_connect_timeout=2,
        socket_timeout=2,
        decode_responses=True,
    )
    key = f"groundstack-ci:{uuid.uuid4().hex}"
    try:
        assert client.ping()
        client.set(key, "integration-ok", ex=30)
        assert client.get(key) == "integration-ok"
    finally:
        client.delete(key)
        client.close()
