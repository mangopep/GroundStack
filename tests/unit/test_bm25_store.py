"""Unit tests for BM25Store."""

from unittest.mock import MagicMock, patch

import pytest

from src.stores.bm25 import BM25Store


class TestBM25Store:
    """Tests for BM25Store class."""

    @patch("src.stores.bm25.OpenSearch")
    def test_init_with_defaults(self, mock_opensearch):
        """Test initialization with default settings."""
        store = BM25Store(verify_connection=False)

        assert store._host == "localhost"
        assert store._port == 9200
        assert store._index == "rag_chunks"
        mock_opensearch.assert_called_once()

    @patch("src.stores.bm25.OpenSearch")
    def test_init_with_custom_index(self, mock_opensearch):
        """Test initialization with custom index name."""
        store = BM25Store(index_name="custom_index", verify_connection=False)

        assert store._index == "custom_index"

    @patch("src.stores.bm25.OpenSearch")
    def test_init_reads_env_vars(self, mock_opensearch):
        """Test initialization reads from environment variables."""
        with patch.dict("os.environ", {
            "OPENSEARCH_HOST": "192.168.1.1",
            "OPENSEARCH_PORT": "9201",
            "OPENSEARCH_INDEX": "my_index"
        }):
            store = BM25Store(verify_connection=False)

            assert store._host == "192.168.1.1"
            assert store._port == 9201
            assert store._index == "my_index"

    @patch("src.stores.bm25.OpenSearch")
    def test_verify_connection_success(self, mock_opensearch):
        """Test connection verification succeeds."""
        mock_client = MagicMock()
        mock_client.ping.return_value = True
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=True)

        mock_client.ping.assert_called_once()

    @patch("src.stores.bm25.OpenSearch")
    def test_verify_connection_failure(self, mock_opensearch):
        """Test connection verification fails when ping returns False."""
        mock_client = MagicMock()
        mock_client.ping.return_value = False
        mock_opensearch.return_value = mock_client

        with pytest.raises(ConnectionError):
            BM25Store(verify_connection=True)

    def test_chunk_to_document_from_dict(self):
        """Test converting dict-like chunk to document."""
        store = BM25Store(verify_connection=False)

        chunk = {
            "id": "chunk1",
            "doc_id": "doc1",
            "title": "Test Title",
            "content": "Test content",
            "section_path": "Chapter 1",
            "page_numbers": [5],
            "chunk_type": "section",
            "parent_id": None,
            "is_structural": False,
        }

        doc = store._chunk_to_document(chunk)

        assert doc["id"] == "chunk1"
        assert doc["doc_id"] == "doc1"
        assert doc["title"] == "Test Title"
        assert doc["content"] == "Test content"
        assert doc["section_path"] == "Chapter 1"
        assert doc["page_numbers"] == [5]
        assert doc["chunk_type"] == "section"
        assert doc["is_structural"] is False

    def test_chunk_to_document_with_pydantic_model(self):
        """Test converting Pydantic model to document."""
        from pydantic import BaseModel

        store = BM25Store(verify_connection=False)

        class ChunkModel(BaseModel):
            id: str
            doc_id: str
            title: str
            content: str
            section_path: str | None = None
            page_numbers: list[int] | None = None

        chunk = ChunkModel(
            id="chunk1",
            doc_id="doc1",
            title="Test",
            content="Content"
        )

        doc = store._chunk_to_document(chunk)

        assert doc["id"] == "chunk1"
        assert doc["content"] == "Content"

    def test_chunk_to_document_normalizes_page_numbers_none(self):
        """Test page_numbers normalization when None."""
        store = BM25Store(verify_connection=False)

        chunk = {"id": "c1", "doc_id": "d1", "content": "test", "page_numbers": None}

        doc = store._chunk_to_document(chunk)

        assert doc["page_numbers"] == []

    def test_chunk_to_document_normalizes_page_numbers_scalar(self):
        """Test page_numbers normalization when scalar."""
        store = BM25Store(verify_connection=False)

        chunk = {"id": "c1", "doc_id": "d1", "content": "test", "page_numbers": 5}

        doc = store._chunk_to_document(chunk)

        assert doc["page_numbers"] == [5]

    def test_chunk_to_document_filters_none_values(self):
        """Test that None values are filtered from document."""
        store = BM25Store(verify_connection=False)

        chunk = {"id": "c1", "doc_id": "d1", "content": "test", "title": None}

        doc = store._chunk_to_document(chunk)

        assert "title" not in doc

    def test_format_search_hit_basic(self):
        """Test formatting search hit basic fields."""
        store = BM25Store(verify_connection=False)

        hit = {
            "_score": 3.5,
            "_source": {
                "id": "abc123",
                "title": "Example",
                "content": "This is content",
                "section_path": "Chapter 1",
                "page_numbers": [5],
                "doc_id": "doc1",
                "chunk_type": "section"
            }
        }

        result = store._format_search_hit(hit)

        assert result["chunk_id"] == "abc123"
        assert result["title"] == "Example"
        assert result["content"] == "This is content"
        assert result["score"] == 3.5
        assert result["section_path"] == "Chapter 1"
        assert result["page_number"] == 5
        assert result["doc_id"] == "doc1"
        assert result["chunk_type"] == "section"

    def test_format_search_hit_no_page_numbers(self):
        """Test formatting search hit when page_numbers is missing."""
        store = BM25Store(verify_connection=False)

        hit = {
            "_score": 1.0,
            "_source": {
                "id": "abc",
                "content": "content",
                "doc_id": "doc"
            }
        }

        result = store._format_search_hit(hit)

        assert result["page_number"] is None

    def test_format_search_hit_empty_page_numbers(self):
        """Test formatting search hit when page_numbers is empty list."""
        store = BM25Store(verify_connection=False)

        hit = {
            "_score": 1.0,
            "_source": {
                "id": "abc",
                "content": "content",
                "doc_id": "doc",
                "page_numbers": []
            }
        }

        result = store._format_search_hit(hit)

        assert result["page_number"] is None

    @patch("src.stores.bm25.OpenSearch")
    def test_index_chunk_success(self, mock_opensearch):
        """Test successful chunk indexing."""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=False)

        chunk = {
            "id": "chunk1",
            "doc_id": "doc1",
            "title": "Test",
            "content": "Test content",
            "section_path": "Ch1",
            "page_numbers": [1],
            "chunk_type": "section",
            "is_structural": False
        }

        store.index_chunk(chunk)

        mock_client.index.assert_called_once()
        call_args = mock_client.index.call_args
        assert call_args.kwargs["id"] == "chunk1"
        assert call_args.kwargs["index"] == "rag_chunks"

    @patch("src.stores.bm25.OpenSearch")
    def test_index_chunk_validates_id(self, mock_opensearch):
        """Test index_chunk raises ValueError when id is missing."""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=False)

        chunk = {"doc_id": "doc1", "content": "test"}

        with pytest.raises(ValueError, match="id"):
            store.index_chunk(chunk)

    @patch("src.stores.bm25.OpenSearch")
    def test_index_chunk_validates_content(self, mock_opensearch):
        """Test index_chunk raises ValueError when content is missing."""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=False)

        chunk = {"id": "chunk1", "doc_id": "doc1", "content": ""}

        with pytest.raises(ValueError, match="content"):
            store.index_chunk(chunk)

    @patch("src.stores.bm25.OpenSearch")
    def test_index_chunk_validates_doc_id(self, mock_opensearch):
        """Test index_chunk raises ValueError when doc_id is missing."""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=False)

        chunk = {"id": "chunk1", "doc_id": "", "content": "test"}

        with pytest.raises(ValueError, match="doc_id"):
            store.index_chunk(chunk)

    @patch("src.stores.bm25.OpenSearch")
    def test_search_success(self, mock_opensearch):
        """Test successful search."""
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_score": 2.5,
                        "_source": {
                            "id": "chunk1",
                            "title": "Test",
                            "content": "Test content",
                            "section_path": "Ch1",
                            "page_numbers": [1],
                            "doc_id": "doc1",
                            "chunk_type": "section"
                        }
                    }
                ]
            }
        }
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=False)

        results = store.search("test query", top_k=5)

        assert len(results) == 1
        assert results[0]["chunk_id"] == "chunk1"
        assert results[0]["score"] == 2.5

        mock_client.search.assert_called_once()
        call_args = mock_client.search.call_args
        assert call_args.kwargs["index"] == "rag_chunks"

    @patch("src.stores.bm25.OpenSearch")
    def test_search_validates_empty_query(self, mock_opensearch):
        """Test search raises ValueError for empty query."""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=False)

        with pytest.raises(ValueError, match="Query cannot be empty"):
            store.search("")

        with pytest.raises(ValueError, match="Query cannot be empty"):
            store.search("   ")

    @patch("src.stores.bm25.OpenSearch")
    def test_search_validates_top_k(self, mock_opensearch):
        """Test search raises ValueError for invalid top_k."""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=False)

        with pytest.raises(ValueError, match="top_k must be at least 1"):
            store.search("query", top_k=0)

        with pytest.raises(ValueError, match="top_k must be at least 1"):
            store.search("query", top_k=-1)

    @patch("src.stores.bm25.OpenSearch")
    def test_search_returns_empty_for_no_hits(self, mock_opensearch):
        """Test search returns empty list when no hits."""
        mock_client = MagicMock()
        mock_client.search.return_value = {"hits": {"hits": []}}
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=False)

        results = store.search("nonexistent")

        assert results == []

    @patch("src.stores.bm25.OpenSearch")
    def test_delete_by_doc_id_success(self, mock_opensearch):
        """Test successful deletion by doc_id."""
        mock_client = MagicMock()
        mock_client.delete_by_query.return_value = {"deleted": 5}
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=False)

        deleted = store.delete_by_doc_id("doc1")

        assert deleted == 5
        mock_client.delete_by_query.assert_called_once()

    @patch("src.stores.bm25.OpenSearch")
    def test_delete_by_doc_id_validates_input(self, mock_opensearch):
        """Test delete_by_doc_id raises ValueError for empty doc_id."""
        mock_client = MagicMock()
        mock_opensearch.return_value = mock_client

        store = BM25Store(verify_connection=False)

        with pytest.raises(ValueError, match="doc_id cannot be empty"):
            store.delete_by_doc_id("")

        with pytest.raises(ValueError, match="doc_id cannot be empty"):
            store.delete_by_doc_id("   ")

