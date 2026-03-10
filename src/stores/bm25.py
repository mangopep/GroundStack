"""OpenSearch-backed BM25 search wrapper for RAG platform."""

import logging
import os
from typing import Any

from opensearchpy import OpenSearch

from src.config import get_settings

logger = logging.getLogger(__name__)


class BM25Store:
    """BM25 full-text search store backed by OpenSearch."""

    def __init__(self, index_name: str | None = None, verify_connection: bool = True) -> None:
        """
        Initialize BM25Store with OpenSearch connection.

        Args:
            index_name: Optional custom index name. Defaults to OPENSEARCH_INDEX env var.
            verify_connection: Whether to verify connection on init.
        """
        settings = get_settings()
        self._host = os.environ.get("OPENSEARCH_HOST", settings.opensearch_host)
        self._port = int(os.environ.get("OPENSEARCH_PORT", settings.opensearch_port))
        self._index = index_name or os.environ.get("OPENSEARCH_INDEX", settings.opensearch_index)

        self._client = OpenSearch(
            hosts=[{"host": self._host, "port": self._port}],
            use_ssl=False,
            verify_certs=False,
            ssl_show_warn=False,
        )

        if verify_connection:
            self._verify_connection()

    def _verify_connection(self) -> None:
        """Verify OpenSearch connection is working."""
        try:
            if not self._client.ping():
                raise ConnectionError("OpenSearch ping failed")
            logger.info("Connected to OpenSearch at %s:%s", self._host, self._port)
        except Exception as e:
            logger.error("Failed to connect to OpenSearch: %s", e)
            raise

    def _chunk_to_document(self, chunk: Any) -> dict[str, Any]:
        """
        Convert chunk object to OpenSearch document.

        Args:
            chunk: Chunk object with attributes or dict-like access.

        Returns:
            Document dict for indexing.
        """
        if hasattr(chunk, "model_dump"):
            data = chunk.model_dump()
        elif hasattr(chunk, "dict"):
            data = chunk.dict()
        elif hasattr(chunk, "__dict__"):
            data = chunk.__dict__
        else:
            data = dict(chunk)

        doc = {
            "id": data.get("id"),
            "doc_id": data.get("doc_id"),
            "title": data.get("title"),
            "content": data.get("content"),
            "section_path": data.get("section_path"),
            "page_numbers": data.get("page_numbers"),
            "chunk_type": data.get("chunk_type"),
            "parent_id": data.get("parent_id"),
            "is_structural": data.get("is_structural", False),
        }

        # Normalize page_numbers: ensure it's a list
        if "page_numbers" in doc:
            page_nums = doc["page_numbers"]
            if page_nums is None:
                doc["page_numbers"] = []
            elif not isinstance(page_nums, list):
                doc["page_numbers"] = [page_nums]

        return {k: v for k, v in doc.items() if v is not None}

    def _format_search_hit(self, hit: dict[str, Any]) -> dict[str, Any]:
        """
        Format OpenSearch search hit to result dict.

        Args:
            hit: OpenSearch search hit.

        Returns:
            Formatted result dict.
        """
        source = hit.get("_source", {})
        page_numbers = source.get("page_numbers") or []

        # Normalise content: new-path chunks store under 'content',
        # legacy phase1.py chunks store under 'text'.
        content = source.get("content") or source.get("text")
        return {
            "chunk_id": source.get("id") or source.get("chunk_id"),
            "title": source.get("title"),
            "content": content,
            "score": hit.get("_score"),
            "section_path": source.get("section_path"),
            "page_number": page_numbers[0] if page_numbers else None,
            "doc_id": source.get("doc_id"),
            "chunk_type": source.get("chunk_type"),
        }

    def index_chunk(self, chunk: Any, refresh: bool = True) -> None:
        """
        Index a chunk into OpenSearch.

        Args:
            chunk: Chunk object or dict-like with id and content fields.
            refresh: Whether to refresh the index after indexing.
                    Set to False for better bulk ingestion performance.

        Raises:
            ValueError: If chunk is missing required fields (id, content, doc_id).
            Exception: If indexing fails.
        """
        try:
            document = self._chunk_to_document(chunk)
            chunk_id = document.get("id")

            if not chunk_id:
                raise ValueError("Chunk must have an 'id' field")
            if not document.get("content"):
                raise ValueError("Chunk must have a 'content' field")
            if not document.get("doc_id"):
                raise ValueError("Chunk must have a 'doc_id' field")

            self._client.index(
                index=self._index,
                id=chunk_id,
                body=document,
                refresh=refresh,
            )
            logger.debug("Indexed chunk %s to index %s", chunk_id, self._index)
        except Exception as e:
            logger.error("Failed to index chunk: %s", e)
            raise

    def search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """
        Search chunks using BM25 full-text search.

        Args:
            query: Search query string.
            top_k: Number of results to return.

        Returns:
            List of search result dicts with chunk_id, title, content, score,
            section_path, page_number, and doc_id.

        Raises:
            ValueError: If query is empty or top_k is less than 1.
        """
        if not query.strip():
            raise ValueError("Query cannot be empty")
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        search_body = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query,
                                # Search both field names: chunks indexed via
                                # ingest_pdf/BM25Store use 'content'; chunks
                                # indexed via the legacy phase1.py path use 'text'.
                                "fields": ["title^2", "content", "text"],
                                "type": "best_fields",
                            }
                        }
                    ],
                    "filter": [
                        # Exclude chunks where is_structural is explicitly True.
                        # Using must_not instead of a term:false filter so that
                        # legacy chunks (no is_structural field) are also returned.
                        {"bool": {"must_not": [{"term": {"is_structural": True}}]}}
                    ],
                }
            },
            "size": top_k,
            "sort": [{"_score": "desc"}],
        }

        try:
            response = self._client.search(
                index=self._index,
                body=search_body,
            )

            hits = response.get("hits", {}).get("hits", [])
            results = [self._format_search_hit(hit) for hit in hits]

            logger.debug("Search for '%s' returned %d results", query, len(results))
            return results
        except Exception as e:
            logger.error("Search failed: %s", e)
            raise

    def delete_by_doc_id(self, doc_id: str) -> int:
        """
        Delete all chunks belonging to a document.

        Args:
            doc_id: Document ID to delete chunks for.

        Returns:
            Number of deleted documents.

        Raises:
            ValueError: If doc_id is empty.
        """
        if not doc_id or not doc_id.strip():
            raise ValueError("doc_id cannot be empty")

        delete_by_query_body = {
            "query": {
                "term": {
                    "doc_id": doc_id
                }
            }
        }

        try:
            response = self._client.delete_by_query(
                index=self._index,
                body=delete_by_query_body,
                refresh=True,
            )

            deleted = response.get("deleted", 0)
            logger.info("Deleted %d chunks for doc_id %s", deleted, doc_id)
            return deleted
        except Exception as e:
            logger.error("Failed to delete chunks for doc_id %s: %s", doc_id, e)
            raise

