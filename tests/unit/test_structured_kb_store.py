"""
Unit tests for StructuredKBStore.

All database I/O is mocked — these tests verify Python logic only:
  - _row_to_dict() column mapping and JSONB string fallback
  - _normalize_tags() stripping and filtering
  - _serialize_knowledge_object() shapes the dict correctly
  - insert() / search_by_type() / search_by_tags() / get_by_id() call the
    correct SQL with the correct parameters
  - Input validation raises ValueError for bad arguments
  - close() and context-manager protocol work
"""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.schemas.knowledge import CLICommandReference, KnowledgeObject
from src.stores.structured_kb import StructuredKBStore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)


def _make_obj(
    id: str = "obj-1",
    tags: list[str] | None = None,
) -> KnowledgeObject:
    return KnowledgeObject(
        id=id,
        type="cli_command_reference",
        version=1,
        data=CLICommandReference(
            command="docker ps",
            syntax="docker ps [OPTIONS]",
        ),
        chunk_hash="abc123",
        created_at=NOW,
        updated_at=NOW,
        created_by="test",
        tags=tags or ["docker", "linux"],
    )


@pytest.fixture()
def store():
    """Return a StructuredKBStore with pool construction fully mocked."""
    with patch("src.stores.structured_kb.psycopg_pool.ConnectionPool") as mock_pool_cls:
        mock_pool = MagicMock()
        mock_pool_cls.return_value = mock_pool
        with patch("src.stores.structured_kb.get_settings") as mock_settings:
            mock_settings.return_value.database.host = "localhost"
            mock_settings.return_value.database.port = 5432
            mock_settings.return_value.database.user = "rag"
            mock_settings.return_value.database.password = "secret"
            mock_settings.return_value.database.db = "rag_platform"
            s = StructuredKBStore(verify_connection=False)
    # Expose the mock pool for individual tests to configure
    s._pool = mock_pool
    return s


# ---------------------------------------------------------------------------
# _row_to_dict
# ---------------------------------------------------------------------------


class TestRowToDict:
    def test_basic_mapping(self, store):
        row = (
            "id1",
            "cli_command_reference",
            1,
            {"command": "ls"},
            "h1",
            NOW,
            NOW,
            "system",
            ["linux"],
        )
        result = store._row_to_dict(row)

        assert result["id"] == "id1"
        assert result["type"] == "cli_command_reference"
        assert result["version"] == 1
        assert result["data"] == {"command": "ls"}
        assert result["chunk_hash"] == "h1"
        assert result["created_by"] == "system"
        assert result["tags"] == ["linux"]

    def test_includes_score_when_requested(self, store):
        row = ("id1", "cli_command_reference", 1, {}, "h1", NOW, NOW, "sys", [], 0.95)
        result = store._row_to_dict(row, include_score=True)

        assert result["score"] == 0.95

    def test_data_string_fallback(self, store):
        """data returned as JSON string (fallback path) is decoded to dict."""
        row = (
            "id1",
            "cli_command_reference",
            1,
            json.dumps({"command": "ls"}),
            "h1",
            NOW,
            NOW,
            "sys",
            [],
        )
        result = store._row_to_dict(row)

        assert isinstance(result["data"], dict)
        assert result["data"]["command"] == "ls"

    def test_tags_string_fallback(self, store):
        """tags returned as JSON string (fallback path) is decoded to list."""
        row = (
            "id1",
            "cli_command_reference",
            1,
            {},
            "h1",
            NOW,
            NOW,
            "sys",
            json.dumps(["linux", "docker"]),
        )
        result = store._row_to_dict(row)

        assert isinstance(result["tags"], list)
        assert result["tags"] == ["linux", "docker"]


# ---------------------------------------------------------------------------
# _normalize_tags
# ---------------------------------------------------------------------------


class TestNormalizeTags:
    def test_strips_whitespace(self, store):
        assert store._normalize_tags(["  linux  ", "docker"]) == ["linux", "docker"]

    def test_removes_empty_strings(self, store):
        assert store._normalize_tags(["", "linux", " "]) == ["linux"]

    def test_empty_list(self, store):
        assert store._normalize_tags([]) == []

    def test_all_empty(self, store):
        assert store._normalize_tags(["", "  "]) == []


# ---------------------------------------------------------------------------
# _serialize_knowledge_object
# ---------------------------------------------------------------------------


class TestSerializeKnowledgeObject:
    def test_keys_present(self, store):
        obj = _make_obj()
        result = store._serialize_knowledge_object(obj)

        assert set(result.keys()) == {
            "id",
            "type",
            "version",
            "data",
            "chunk_hash",
            "created_at",
            "updated_at",
            "created_by",
            "tags",
        }

    def test_id_and_type(self, store):
        obj = _make_obj(id="xyz")
        result = store._serialize_knowledge_object(obj)

        assert result["id"] == "xyz"
        assert result["type"] == "cli_command_reference"

    def test_data_is_jsonb_wrapper(self, store):
        from psycopg.types.json import Jsonb

        obj = _make_obj()
        result = store._serialize_knowledge_object(obj)

        assert isinstance(result["data"], Jsonb)

    def test_tags_is_jsonb_wrapper(self, store):
        from psycopg.types.json import Jsonb

        obj = _make_obj(tags=["docker", "linux"])
        result = store._serialize_knowledge_object(obj)

        assert isinstance(result["tags"], Jsonb)


# ---------------------------------------------------------------------------
# insert
# ---------------------------------------------------------------------------


class TestInsert:
    def test_executes_upsert(self, store):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        store._pool.connection.return_value = mock_conn

        store.insert(_make_obj())

        mock_cur.execute.assert_called_once()
        sql = mock_cur.execute.call_args[0][0]
        assert "INSERT INTO structured_kb" in sql
        assert "ON CONFLICT (id) DO UPDATE" in sql
        # Redundant WHERE clause must NOT appear
        assert "WHERE structured_kb.id = EXCLUDED.id" not in sql

    def test_commit_is_called(self, store):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_conn.cursor.return_value = mock_cur
        store._pool.connection.return_value = mock_conn

        store.insert(_make_obj())

        mock_conn.commit.assert_called_once()

    def test_db_error_propagates(self, store):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.execute.side_effect = RuntimeError("DB down")
        mock_conn.cursor.return_value = mock_cur
        store._pool.connection.return_value = mock_conn

        with pytest.raises(RuntimeError, match="DB down"):
            store.insert(_make_obj())


# ---------------------------------------------------------------------------
# search_by_type
# ---------------------------------------------------------------------------


class TestSearchByType:
    def _setup_cursor(self, store, rows):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchall.return_value = rows
        mock_conn.cursor.return_value = mock_cur
        store._pool.connection.return_value = mock_conn
        return mock_cur

    def test_returns_results_with_score(self, store):
        row = (
            "id1",
            "cli_command_reference",
            1,
            {"command": "ls"},
            "h1",
            NOW,
            NOW,
            "sys",
            ["linux"],
            0.87,
        )
        self._setup_cursor(store, [row])

        results = store.search_by_type("cli_command_reference", "docker")

        assert len(results) == 1
        assert results[0]["id"] == "id1"
        assert results[0]["score"] == 0.87

    def test_sql_uses_knowledge_type_param(self, store):
        cur = self._setup_cursor(store, [])

        store.search_by_type("cli_command_reference", "docker", limit=5)

        sql, params = cur.execute.call_args[0]
        assert "WHERE type = %s" in sql
        assert params == ("docker", "cli_command_reference", "docker", 5)

    def test_empty_type_raises(self, store):
        with pytest.raises(ValueError, match="knowledge_type cannot be empty"):
            store.search_by_type("", "docker")

    def test_empty_query_raises(self, store):
        with pytest.raises(ValueError, match="query cannot be empty"):
            store.search_by_type("cli_command_reference", "")

    def test_limit_below_one_raises(self, store):
        with pytest.raises(ValueError, match="limit must be >= 1"):
            store.search_by_type("cli_command_reference", "docker", limit=0)


# ---------------------------------------------------------------------------
# search_by_tags
# ---------------------------------------------------------------------------


class TestSearchByTags:
    def _setup_cursor(self, store, rows):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchall.return_value = rows
        mock_conn.cursor.return_value = mock_cur
        store._pool.connection.return_value = mock_conn
        return mock_cur

    def test_returns_results(self, store):
        row = ("id1", "cli_command_reference", 1, {}, "h1", NOW, NOW, "sys", ["linux"])
        self._setup_cursor(store, [row])

        results = store.search_by_tags(["linux"])

        assert len(results) == 1
        assert results[0]["id"] == "id1"

    def test_sql_uses_exists_any_not_interpolation(self, store):
        """Critical: SQL must not contain f-string-injected tag values."""
        cur = self._setup_cursor(store, [])

        store.search_by_tags(["linux", "docker"])

        sql, params = cur.execute.call_args[0]
        # Must use the safe EXISTS / ANY pattern
        assert "EXISTS" in sql
        assert "jsonb_array_elements_text" in sql
        assert "ANY(%s)" in sql
        # Tag values must NOT appear literally in the SQL string
        assert "linux" not in sql
        assert "docker" not in sql
        # Tags passed as a single array parameter
        assert params == (["linux", "docker"],)

    def test_empty_tags_after_normalization_raises(self, store):
        with pytest.raises(ValueError, match="tags list cannot be empty"):
            store.search_by_tags(["", "  "])

    def test_empty_list_raises(self, store):
        with pytest.raises(ValueError, match="tags list cannot be empty"):
            store.search_by_tags([])

    def test_whitespace_tags_stripped(self, store):
        cur = self._setup_cursor(store, [])

        store.search_by_tags(["  linux  "])

        _, params = cur.execute.call_args[0]
        assert params == (["linux"],)


# ---------------------------------------------------------------------------
# get_by_id
# ---------------------------------------------------------------------------


class TestGetById:
    def _setup_cursor(self, store, row):
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_cur.__enter__ = MagicMock(return_value=mock_cur)
        mock_cur.__exit__ = MagicMock(return_value=False)
        mock_cur.fetchone.return_value = row
        mock_conn.cursor.return_value = mock_cur
        store._pool.connection.return_value = mock_conn
        return mock_cur

    def test_returns_dict_when_found(self, store):
        row = (
            "id1",
            "cli_command_reference",
            1,
            {"command": "ls"},
            "h1",
            NOW,
            NOW,
            "sys",
            ["linux"],
        )
        self._setup_cursor(store, row)

        result = store.get_by_id("id1")

        assert result is not None
        assert result["id"] == "id1"

    def test_returns_none_when_not_found(self, store):
        self._setup_cursor(store, None)

        result = store.get_by_id("missing")

        assert result is None

    def test_empty_id_raises(self, store):
        with pytest.raises(ValueError, match="id cannot be empty"):
            store.get_by_id("")

    def test_whitespace_id_raises(self, store):
        with pytest.raises(ValueError, match="id cannot be empty"):
            store.get_by_id("   ")


# ---------------------------------------------------------------------------
# close / context manager
# ---------------------------------------------------------------------------


class TestLifecycle:
    def test_close_calls_pool_close(self, store):
        store.close()
        store._pool.close.assert_called_once()

    def test_context_manager(self):
        with patch("src.stores.structured_kb.psycopg_pool.ConnectionPool") as mock_pool_cls:
            mock_pool = MagicMock()
            mock_pool_cls.return_value = mock_pool
            with patch("src.stores.structured_kb.get_settings") as mock_settings:
                mock_settings.return_value.database.host = "localhost"
                mock_settings.return_value.database.port = 5432
                mock_settings.return_value.database.user = "rag"
                mock_settings.return_value.database.password = "secret"
                mock_settings.return_value.database.db = "rag_platform"
                with StructuredKBStore(verify_connection=False) as s:
                    assert isinstance(s, StructuredKBStore)
            mock_pool.close.assert_called_once()
