"""
23-test unit suite for src/ingestion/index_builder.py.

Covers:
  - compute_doc_id (determinism, uniqueness, output format)
  - compute_chunk_hash (determinism, content sensitivity, empty content)
  - infer_table_kb_type (RCA match, CLI match, partial matches, priority)
  - ingest_pdf (happy path, validation errors, per-chunk failures,
                table extraction, fatal failures, store lifecycle, LangFuse)

Run with:
    pytest tests/unit/test_index_builder.py -v
"""

import contextlib
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.chunker import ChunkResult
from src.ingestion.index_builder import (
    compute_chunk_hash,
    compute_doc_id,
    infer_table_kb_type,
    ingest_pdf,
)

# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------

MODULE = "src.ingestion.index_builder"


def _make_chunk(
    chunk_id: str = "chunk001",
    chunk_type: str = "section",
    content: str = "Some body text",
    page_numbers: list[int] | None = None,
) -> ChunkResult:
    """Minimal valid ChunkResult."""
    return ChunkResult(
        id=chunk_id,
        title="Test Section",
        content=content,
        section_path="Doc > Section",
        page_numbers=page_numbers or [1],
        chunk_type=chunk_type,
        doc_id="doc001",
        is_structural=False,
    )


def _fake_pages(count: int = 2) -> list:
    """Return a list of `count` MagicMock page objects."""
    return [MagicMock() for _ in range(count)]


@contextlib.contextmanager
def _patch_ingest(
    fake_pdf: Path,
    chunks: list[ChunkResult] | None = None,
    bm25_side_effect=None,
    kb_insert_side_effect=None,
    upload_side_effect=None,
    metadata_side_effect=None,
    upload_return: str = "docs/doc0/sample.pdf",
):
    """
    Patch all external I/O in ingest_pdf and yield a dict of mocks.

    Usage::

        with _patch_ingest(fake_pdf, chunks=[...]) as mocks:
            result = ingest_pdf(fake_pdf)
            mocks["bm25"].index_chunk.assert_called()
    """
    if chunks is None:
        chunks = [_make_chunk(chunk_id="c1"), _make_chunk(chunk_id="c2")]

    mock_bm25 = MagicMock()
    if bm25_side_effect:
        mock_bm25.index_chunk.side_effect = bm25_side_effect

    mock_kb_instance = MagicMock()
    if kb_insert_side_effect:
        mock_kb_instance.insert.side_effect = kb_insert_side_effect
    mock_kb_cls = MagicMock()
    mock_kb_cls.return_value.__enter__.return_value = mock_kb_instance
    mock_kb_cls.return_value.__exit__.return_value = False

    mock_doc = MagicMock()
    if upload_side_effect:
        mock_doc.upload_pdf.side_effect = upload_side_effect
    else:
        mock_doc.upload_pdf.return_value = upload_return

    with (
        patch(f"{MODULE}.process_pdf", return_value=_fake_pages()) as pp,
        patch(f"{MODULE}.chunk_pages", return_value=chunks) as cp,
        patch(f"{MODULE}.BM25Store", return_value=mock_bm25),
        patch(f"{MODULE}.StructuredKBStore", mock_kb_cls),
        patch(f"{MODULE}.DocStore", return_value=mock_doc),
        patch(f"{MODULE}._upsert_document_metadata", side_effect=metadata_side_effect) as um,
        patch(f"{MODULE}._log_langfuse_event") as lf,
    ):
        yield {
            "process_pdf": pp,
            "chunk_pages": cp,
            "bm25": mock_bm25,
            "kb": mock_kb_instance,
            "kb_cls": mock_kb_cls,
            "doc": mock_doc,
            "upsert": um,
            "langfuse": lf,
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_pdf(tmp_path: Path) -> Path:
    """A minimal .pdf file that actually exists on disk."""
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.4 header")
    return p


# ===========================================================================
# compute_doc_id
# ===========================================================================


class TestComputeDocId:
    def test_deterministic(self, tmp_path: Path):
        """Same path always produces the same doc_id."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        assert compute_doc_id(pdf) == compute_doc_id(pdf)

    def test_different_paths_differ(self, tmp_path: Path):
        """Two distinct paths produce different doc_ids."""
        a = tmp_path / "a.pdf"
        b = tmp_path / "b.pdf"
        a.write_bytes(b"%PDF-1.4")
        b.write_bytes(b"%PDF-1.4")
        assert compute_doc_id(a) != compute_doc_id(b)

    def test_returns_16_hex_chars(self, tmp_path: Path):
        """doc_id is exactly 16 lowercase hex characters."""
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF-1.4")
        doc_id = compute_doc_id(pdf)
        assert len(doc_id) == 16
        assert all(c in "0123456789abcdef" for c in doc_id)


# ===========================================================================
# compute_chunk_hash
# ===========================================================================


class TestComputeChunkHash:
    def test_deterministic(self):
        """Same content always produces the same hash."""
        chunk = _make_chunk(content="hello world")
        assert compute_chunk_hash(chunk) == compute_chunk_hash(chunk)

    def test_different_content_differs(self):
        """Different content produces different hashes."""
        a = _make_chunk(chunk_id="c1", content="hello")
        b = _make_chunk(chunk_id="c2", content="world")
        assert compute_chunk_hash(a) != compute_chunk_hash(b)

    def test_empty_content_yields_sha256_of_empty_string(self):
        """Empty content maps to SHA-256('') — not an error."""
        chunk = _make_chunk(content="")
        assert compute_chunk_hash(chunk) == hashlib.sha256(b"").hexdigest()


# ===========================================================================
# infer_table_kb_type
# ===========================================================================


class TestInferTableKbType:
    def test_rca_keywords_match(self):
        """≥2 RCA keywords → root_cause_analysis."""
        content = "Symptom: crash. Root Cause: OOM. Fix: restart. Severity: S1"
        assert infer_table_kb_type(content) == "root_cause_analysis"

    def test_cli_keywords_match(self):
        """≥2 CLI keywords → cli_command_reference."""
        content = "Command: run. Syntax: run [args]. Parameter: --flag. Example: run --debug"
        assert infer_table_kb_type(content) == "cli_command_reference"

    def test_single_rca_keyword_no_match(self):
        """1 RCA keyword is below threshold → None."""
        assert infer_table_kb_type("symptom: disk full") is None

    def test_single_cli_keyword_no_match(self):
        """1 CLI keyword is below threshold → None."""
        assert infer_table_kb_type("example of something") is None

    def test_empty_content_returns_none(self):
        assert infer_table_kb_type("") is None

    def test_rca_takes_priority_when_both_thresholds_met(self):
        """RCA branch executes first — wins if its threshold is met too."""
        content = "symptom root cause fix severity command syntax"
        assert infer_table_kb_type(content) == "root_cause_analysis"


# ===========================================================================
# ingest_pdf
# ===========================================================================


class TestIngestPdf:
    # --- Input validation ---------------------------------------------------

    def test_file_not_found_raises(self, tmp_path: Path):
        missing = tmp_path / "ghost.pdf"
        with pytest.raises(FileNotFoundError, match="ghost.pdf"):
            ingest_pdf(missing)

    def test_non_pdf_extension_raises(self, tmp_path: Path):
        txt = tmp_path / "document.txt"
        txt.write_text("not a pdf")
        with pytest.raises(ValueError, match=r"\.txt"):
            ingest_pdf(txt)

    # --- Happy path ---------------------------------------------------------

    def test_valid_pdf_returns_correct_result(self, fake_pdf: Path):
        chunks = [_make_chunk(chunk_id="c1"), _make_chunk(chunk_id="c2")]
        with _patch_ingest(fake_pdf, chunks=chunks):
            result = ingest_pdf(fake_pdf)

        assert result.filename == "sample.pdf"
        assert result.page_count == 2  # _fake_pages() returns 2
        assert result.chunk_count == 2
        assert result.indexed_chunk_count == 2
        assert result.table_chunk_count == 0
        assert result.structured_kb_count == 0
        assert result.status == "success"
        assert result.warnings == []
        assert result.uploaded_pdf_key == "docs/doc0/sample.pdf"

    def test_all_stores_called_on_happy_path(self, fake_pdf: Path):
        with _patch_ingest(fake_pdf) as mocks:
            ingest_pdf(fake_pdf)

        mocks["bm25"].index_chunk.assert_called()
        mocks["doc"].upload_pdf.assert_called_once()
        mocks["upsert"].assert_called_once()
        mocks["langfuse"].assert_called_once()

    # --- Per-chunk BM25 failure (non-fatal) ---------------------------------

    def test_bm25_failure_continues_with_warning(self, fake_pdf: Path):
        chunks = [_make_chunk(chunk_id="c1"), _make_chunk(chunk_id="c2")]
        with _patch_ingest(
            fake_pdf,
            chunks=chunks,
            bm25_side_effect=RuntimeError("OpenSearch down"),
        ):
            result = ingest_pdf(fake_pdf)

        assert result.indexed_chunk_count == 0
        assert result.status == "partial"
        assert len(result.warnings) == 2
        assert all("Failed to index chunk" in w for w in result.warnings)

    # --- Table extraction ---------------------------------------------------

    def test_table_chunk_rca_triggers_kb_insert(self, fake_pdf: Path):
        table_chunk = _make_chunk(
            chunk_id="t1",
            chunk_type="table",
            content="Symptom: crash. Root Cause: OOM. Fix: restart. Severity: S1",
        )
        with _patch_ingest(fake_pdf, chunks=[table_chunk]) as mocks:
            result = ingest_pdf(fake_pdf)

        mocks["kb"].insert.assert_called_once()
        assert result.structured_kb_count == 1
        assert result.table_chunk_count == 1

    def test_table_chunk_cli_triggers_kb_insert(self, fake_pdf: Path):
        table_chunk = _make_chunk(
            chunk_id="t2",
            chunk_type="table",
            content="Command: run. Syntax: run [args]. Parameter: --flag. Example: run --debug",
        )
        with _patch_ingest(fake_pdf, chunks=[table_chunk]) as mocks:
            result = ingest_pdf(fake_pdf)

        mocks["kb"].insert.assert_called_once()
        assert result.structured_kb_count == 1

    def test_table_chunk_no_keywords_skips_kb_insert(self, fake_pdf: Path):
        table_chunk = _make_chunk(
            chunk_id="t3",
            chunk_type="table",
            content="Column A | Column B | Column C",
        )
        with _patch_ingest(fake_pdf, chunks=[table_chunk]) as mocks:
            result = ingest_pdf(fake_pdf)

        mocks["kb"].insert.assert_not_called()
        assert result.structured_kb_count == 0

    def test_kb_insert_failure_continues_with_warning(self, fake_pdf: Path):
        table_chunk = _make_chunk(
            chunk_id="t4",
            chunk_type="table",
            content="Symptom: crash. Root Cause: OOM. Fix: restart. Severity: S1",
        )
        with _patch_ingest(
            fake_pdf,
            chunks=[table_chunk],
            kb_insert_side_effect=RuntimeError("KB insert failed"),
        ):
            result = ingest_pdf(fake_pdf)

        assert result.structured_kb_count == 0
        assert result.status == "partial"
        assert any("root_cause_analysis" in w for w in result.warnings)

    # --- Fatal failures -----------------------------------------------------

    def test_pdf_upload_failure_raises(self, fake_pdf: Path):
        with _patch_ingest(
            fake_pdf,
            upload_side_effect=OSError("MinIO unreachable"),
        ):
            with pytest.raises(OSError, match="MinIO unreachable"):
                ingest_pdf(fake_pdf)

    def test_metadata_write_failure_raises(self, fake_pdf: Path):
        with _patch_ingest(
            fake_pdf,
            metadata_side_effect=RuntimeError("PG down"),
        ):
            with pytest.raises(RuntimeError, match="PG down"):
                ingest_pdf(fake_pdf)

    # --- Store lifecycle ----------------------------------------------------

    def test_structured_kb_store_closed_after_ingestion(self, fake_pdf: Path):
        """StructuredKBStore.__exit__ is called — pool is always released."""
        with _patch_ingest(fake_pdf) as mocks:
            ingest_pdf(fake_pdf)

        mocks["kb_cls"].return_value.__exit__.assert_called_once()

    def test_structured_kb_store_closed_on_upload_failure(self, fake_pdf: Path):
        """StructuredKBStore.__exit__ is called even when a later step fails."""
        with _patch_ingest(
            fake_pdf,
            upload_side_effect=OSError("MinIO down"),
        ) as mocks:
            with pytest.raises(OSError):
                ingest_pdf(fake_pdf)

        mocks["kb_cls"].return_value.__exit__.assert_called_once()

    # --- LangFuse -----------------------------------------------------------

    def test_langfuse_emitted_with_correct_status_on_success(self, fake_pdf: Path):
        with _patch_ingest(fake_pdf) as mocks:
            result = ingest_pdf(fake_pdf)

        mocks["langfuse"].assert_called_once()
        assert mocks["langfuse"].call_args.kwargs["status"] == "success"
        assert mocks["langfuse"].call_args.kwargs["doc_id"] == result.doc_id

    def test_langfuse_emitted_with_partial_on_bm25_failure(self, fake_pdf: Path):
        with _patch_ingest(
            fake_pdf,
            bm25_side_effect=RuntimeError("ES down"),
        ) as mocks:
            ingest_pdf(fake_pdf)

        assert mocks["langfuse"].call_args.kwargs["status"] == "partial"
