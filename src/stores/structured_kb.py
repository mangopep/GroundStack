"""
PostgreSQL-backed JSONB store for structured knowledge objects in a RAG platform.

Implements StructuredKBStore for upserting and searching structured knowledge
objects using PostgreSQL JSONB columns and full-text search.
"""

import json
import logging
from typing import Any

import psycopg_pool
from psycopg.types.json import Jsonb

from src.config.settings import get_settings
from src.schemas.knowledge import KnowledgeObject

logger = logging.getLogger(__name__)


class StructuredKBStore:
    """
    PostgreSQL-backed JSONB store for structured knowledge objects.

    Supports:
    - Upserting structured knowledge objects
    - Full-text search by knowledge type
    - Tag-based lookup using JSONB
    - Fetching by ID
    """

    def __init__(
        self,
        min_size: int = 2,
        max_size: int = 10,
        verify_connection: bool = True,
    ) -> None:
        """
        Initialize StructuredKBStore with connection pool.

        Args:
            min_size: Minimum pool size.
            max_size: Maximum pool size.
            verify_connection: Whether to verify connectivity on init.
        """
        self._pool = psycopg_pool.ConnectionPool(
            conninfo=self._build_dsn(),
            min_size=min_size,
            max_size=max_size,
            kwargs={"autocommit": False},
        )

        if verify_connection:
            self._verify_connection()

    def _build_dsn(self) -> str:
        """Build PostgreSQL DSN from centralized settings."""
        cfg = get_settings().database
        return (
            f"host={cfg.host} port={cfg.port} user={cfg.user} "
            f"password={cfg.password} dbname={cfg.db}"
        )

    def _verify_connection(self) -> None:
        """Verify database connectivity."""
        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            logger.info("Connected to PostgreSQL successfully")
        except Exception as e:
            logger.error("Failed to connect to PostgreSQL: %s", e)
            raise

    def _serialize_knowledge_object(self, obj: KnowledgeObject) -> dict[str, Any]:
        """
        Serialize KnowledgeObject to database-compatible dict.

        Args:
            obj: KnowledgeObject to serialize.

        Returns:
            Dict ready for database insertion.
        """
        return {
            "id": obj.id,
            "type": obj.type,
            "version": obj.version,
            "data": Jsonb(json.loads(obj.model_dump_json())["data"]),
            "chunk_hash": obj.chunk_hash,
            "created_at": obj.created_at,
            "updated_at": obj.updated_at,
            "created_by": obj.created_by,
            "tags": Jsonb(obj.tags),
        }

    def _row_to_dict(self, row: tuple, include_score: bool = False) -> dict[str, Any]:
        """
        Convert database row to dict.

        Args:
            row: Database row tuple.
            include_score: Whether to include search score in result.

        Returns:
            Dict with row data.
        """
        base_cols = [
            "id",
            "type",
            "version",
            "data",
            "chunk_hash",
            "created_at",
            "updated_at",
            "created_by",
            "tags",
        ]

        if include_score:
            base_cols.append("score")

        result = dict(zip(base_cols, row))

        # psycopg may return JSONB columns as str depending on adapter config
        if isinstance(result.get("data"), str):
            result["data"] = json.loads(result["data"])
        if isinstance(result.get("tags"), str):
            result["tags"] = json.loads(result["tags"])

        return result

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        """
        Normalize tags by removing empty strings.

        Args:
            tags: List of tags.

        Returns:
            List of non-empty tags.
        """
        return [tag.strip() for tag in tags if tag and tag.strip()]

    def insert(self, obj: KnowledgeObject) -> None:
        """
        Upsert a knowledge object into the database.

        Args:
            obj: KnowledgeObject to upsert.

        Raises:
            ValueError: If object validation fails.
            Exception: If database operation fails.
        """
        try:
            data = self._serialize_knowledge_object(obj)

            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO structured_kb (
                            id, type, version, data, chunk_hash,
                            created_at, updated_at, created_by, tags
                        ) VALUES (
                            %(id)s, %(type)s, %(version)s, %(data)s, %(chunk_hash)s,
                            %(created_at)s, %(updated_at)s, %(created_by)s, %(tags)s
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            type = EXCLUDED.type,
                            version = EXCLUDED.version,
                            data = EXCLUDED.data,
                            chunk_hash = EXCLUDED.chunk_hash,
                            updated_at = EXCLUDED.updated_at,
                            created_by = EXCLUDED.created_by,
                            tags = EXCLUDED.tags
                        """,
                        data,
                    )
                conn.commit()

            logger.debug("Upserted knowledge object with id=%s", obj.id)

        except Exception as e:
            logger.error("Failed to insert knowledge object: %s", e)
            raise

    def search_by_type(
        self,
        knowledge_type: str,
        query: str,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Search knowledge objects by type using full-text search on JSONB data.

        Args:
            knowledge_type: Knowledge type to filter by.
            query: Full-text search query.
            limit: Maximum number of results.

        Returns:
            List of matching knowledge objects with search score.

        Raises:
            ValueError: If inputs are invalid.
        """
        if not knowledge_type or not knowledge_type.strip():
            raise ValueError("knowledge_type cannot be empty")
        if not query or not query.strip():
            raise ValueError("query cannot be empty")
        if limit < 1:
            raise ValueError("limit must be >= 1")

        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            id, type, version, data, chunk_hash,
                            created_at, updated_at, created_by, tags,
                            ts_rank(
                                to_tsvector('english', data::text),
                                plainto_tsquery('english', %s)
                            ) AS score
                        FROM structured_kb
                        WHERE type = %s
                          AND to_tsvector('english', data::text)
                              @@ plainto_tsquery('english', %s)
                        ORDER BY score DESC
                        LIMIT %s
                        """,
                        (query, knowledge_type, query, limit),
                    )
                    rows = cur.fetchall()

            results = [self._row_to_dict(row, include_score=True) for row in rows]
            logger.debug(
                "search_by_type(knowledge_type=%s, query=%s) returned %d results",
                knowledge_type,
                query,
                len(results),
            )
            return results

        except Exception as e:
            logger.error("Failed to search by type: %s", e)
            raise

    def search_by_tags(self, tags: list[str]) -> list[dict[str, Any]]:
        """
        Search knowledge objects by tags using JSONB array lookup.

        Args:
            tags: List of tags to search for.

        Returns:
            List of matching knowledge objects.

        Raises:
            ValueError: If tags list is empty.
        """
        normalized = self._normalize_tags(tags)
        if not normalized:
            raise ValueError("tags list cannot be empty after normalization")

        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            id, type, version, data, chunk_hash,
                            created_at, updated_at, created_by, tags
                        FROM structured_kb
                        WHERE EXISTS (
                            SELECT 1
                            FROM jsonb_array_elements_text(tags) AS t(val)
                            WHERE t.val = ANY(%s)
                        )
                        """,
                        (normalized,),
                    )
                    rows = cur.fetchall()

            results = [self._row_to_dict(row) for row in rows]
            logger.debug(
                "search_by_tags(tags=%s) returned %d results",
                tags,
                len(results),
            )
            return results

        except Exception as e:
            logger.error("Failed to search by tags: %s", e)
            raise

    def get_by_id(self, id: str) -> dict[str, Any] | None:
        """
        Fetch a knowledge object by its ID.

        Args:
            id: Knowledge object ID.

        Returns:
            Knowledge object dict if found, None otherwise.

        Raises:
            ValueError: If id is empty.
        """
        if not id or not id.strip():
            raise ValueError("id cannot be empty")

        try:
            with self._pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT
                            id, type, version, data, chunk_hash,
                            created_at, updated_at, created_by, tags
                        FROM structured_kb
                        WHERE id = %s
                        """,
                        (id,),
                    )
                    row = cur.fetchone()

            if row is None:
                logger.debug("No knowledge object found with id=%s", id)
                return None

            return self._row_to_dict(row)

        except Exception as e:
            logger.error("Failed to get knowledge object by id: %s", e)
            raise

    def close(self) -> None:
        """Close the connection pool."""
        self._pool.close()
        logger.info("Closed PostgreSQL connection pool")

    def __enter__(self) -> "StructuredKBStore":
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()

