"""
Integration tests for StructuredKBStore.

Runs against a real PostgreSQL instance.  Skipped automatically when
POSTGRES_HOST is not set or when the DB is unreachable.

Run with a live DB:
    pytest tests/integration/test_structured_kb_store.py -v

Or via docker-compose:
    docker-compose up -d postgres
    pytest tests/integration/test_structured_kb_store.py -v
"""

import os
import uuid
from datetime import datetime, timezone

import psycopg
import pytest

from src.schemas.knowledge import CLICommandReference, KnowledgeObject
from src.stores.structured_kb import StructuredKBStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 3, 10, 12, 0, 0, tzinfo=timezone.utc)


def _conninfo() -> str:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    user = os.environ.get("POSTGRES_USER", "rag")
    password = os.environ.get("POSTGRES_PASSWORD", "rag_dev_2026")
    db = os.environ.get("POSTGRES_DB", "rag_platform")
    return f"host={host} port={port} user={user} password={password} dbname={db}"


def _db_reachable() -> bool:
    try:
        with psycopg.connect(_conninfo(), connect_timeout=2) as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _db_reachable(),
    reason="PostgreSQL is not reachable — skipping integration tests",
)


@pytest.fixture(scope="module")
def store():
    """One store for the entire module; pooled connections."""
    with StructuredKBStore(min_size=1, max_size=3, verify_connection=True) as s:
        yield s


def _unique_id(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _make_obj(
    obj_id: str | None = None,
    tags: list[str] | None = None,
    command: str = "docker ps",
) -> KnowledgeObject:
    return KnowledgeObject(
        id=obj_id or _unique_id(),
        type="cli_command_reference",
        version=1,
        data=CLICommandReference(
            command=command,
            syntax=f"{command} [OPTIONS]",
        ),
        chunk_hash=uuid.uuid4().hex,
        created_at=NOW,
        updated_at=NOW,
        created_by="integration-test",
        tags=tags or [],
    )


# ---------------------------------------------------------------------------
# 1. insert / upsert
# ---------------------------------------------------------------------------


class TestInsert:
    def test_insert_and_fetch(self, store):
        obj = _make_obj()
        store.insert(obj)

        result = store.get_by_id(obj.id)
        assert result is not None
        assert result["id"] == obj.id
        assert result["type"] == "cli_command_reference"

    def test_upsert_updates_version(self, store):
        obj = _make_obj()
        store.insert(obj)

        updated = _make_obj(obj_id=obj.id, command="docker ps --all")
        updated_obj = KnowledgeObject(
            **{
                **updated.model_dump(),
                "version": 2,
                "id": obj.id,
            }
        )
        store.insert(updated_obj)

        result = store.get_by_id(obj.id)
        assert result["version"] == 2

    def test_created_at_preserved_on_upsert(self, store):
        """created_at must not be overwritten by the upsert."""
        obj = _make_obj()
        store.insert(obj)

        # Re-insert with same id — created_at not in the UPDATE SET list
        store.insert(obj)

        result = store.get_by_id(obj.id)
        # created_at should still equal the original value
        assert result["created_at"].replace(tzinfo=None) == NOW.replace(tzinfo=None)


# ---------------------------------------------------------------------------
# 2. get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    def test_returns_none_for_missing(self, store):
        assert store.get_by_id("does-not-exist-xyz") is None

    def test_data_is_dict(self, store):
        obj = _make_obj()
        store.insert(obj)

        result = store.get_by_id(obj.id)
        assert isinstance(result["data"], dict), (
            f"Expected dict, got {type(result['data'])}"
        )

    def test_tags_is_list(self, store):
        obj = _make_obj(tags=["docker", "linux"])
        store.insert(obj)

        result = store.get_by_id(obj.id)
        assert isinstance(result["tags"], list), (
            f"Expected list, got {type(result['tags'])}"
        )
        assert set(result["tags"]) == {"docker", "linux"}


# ---------------------------------------------------------------------------
# 3. search_by_tags  — the critical JSONB array proof
# ---------------------------------------------------------------------------


class TestSearchByTags:
    def test_finds_object_by_exact_tag(self, store):
        tag = _unique_id("tag")
        obj = _make_obj(tags=[tag, "extra"])
        store.insert(obj)

        results = store.search_by_tags([tag])

        ids = [r["id"] for r in results]
        assert obj.id in ids, f"{obj.id} not found in {ids}"

    def test_or_semantics_matches_any_tag(self, store):
        """OR semantics: a row matching *any* of the tags must be returned."""
        tag_a = _unique_id("tagA")
        tag_b = _unique_id("tagB")
        obj_a = _make_obj(tags=[tag_a])
        obj_b = _make_obj(tags=[tag_b])
        store.insert(obj_a)
        store.insert(obj_b)

        results = store.search_by_tags([tag_a, tag_b])

        ids = [r["id"] for r in results]
        assert obj_a.id in ids
        assert obj_b.id in ids

    def test_no_match_returns_empty(self, store):
        results = store.search_by_tags([_unique_id("nonexistent")])
        assert results == []

    def test_tags_returned_as_list(self, store):
        tag = _unique_id("lt")
        obj = _make_obj(tags=[tag])
        store.insert(obj)

        results = store.search_by_tags([tag])
        match = next(r for r in results if r["id"] == obj.id)
        assert isinstance(match["tags"], list)

    def test_whitespace_tag_normalized(self, store):
        tag = _unique_id("ws")
        obj = _make_obj(tags=[tag])
        store.insert(obj)

        # Leading/trailing whitespace should be stripped before querying
        results = store.search_by_tags([f"  {tag}  "])
        ids = [r["id"] for r in results]
        assert obj.id in ids


# ---------------------------------------------------------------------------
# 4. search_by_type
# ---------------------------------------------------------------------------


class TestSearchByType:
    def test_finds_matching_object(self, store):
        obj = _make_obj(command="kubectl get pods")
        store.insert(obj)

        results = store.search_by_type("cli_command_reference", "kubectl")

        ids = [r["id"] for r in results]
        assert obj.id in ids

    def test_results_have_score(self, store):
        obj = _make_obj(command="helm list releases")
        store.insert(obj)

        results = store.search_by_type("cli_command_reference", "helm")

        assert len(results) > 0
        assert "score" in results[0]
        assert isinstance(results[0]["score"], float)

    def test_limit_respected(self, store):
        for _ in range(3):
            store.insert(_make_obj(command="grep pattern file"))

        results = store.search_by_type("cli_command_reference", "grep", limit=2)

        assert len(results) <= 2

    def test_no_match_returns_empty(self, store):
        results = store.search_by_type(
            "cli_command_reference", "zzznomatchzzz9999"
        )
        assert results == []
