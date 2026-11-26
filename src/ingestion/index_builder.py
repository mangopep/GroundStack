"""
Ingestion orchestrator for RAG platform.

This module coordinates the full PDF ingestion flow:
1. Process PDF into page-level extraction results
2. Chunk those pages into retrieval chunks
3. Index all chunks into BM25
4. Extract selected table chunks into the structured KB using simple heuristics
5. Upload the raw PDF to document storage
6. Insert/update document metadata in PostgreSQL
7. Emit a LangFuse trace/log event
8. Return an IngestResult object with summary stats
"""

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from pydantic import BaseModel, ConfigDict, Field

from src.config.settings import get_settings
from src.ingestion.chunker import ChunkResult, chunk_pages
from src.ingestion.pdf_intelligence import PageResult, process_pdf
from src.schemas.knowledge import (
    CLICommandReference,
    FixDetail,
    KnowledgeObject,
    RootCauseAnalysis,
    RootCauseDetail,
    Source,
)
from src.stores.bm25 import BM25Store
from src.stores.doc_store import DocStore
from src.stores.structured_kb import StructuredKBStore

# Try to import LangFuse, but gracefully handle if unavailable
try:
    from langfuse import Langfuse

    LANGFUSE_AVAILABLE = True
except (ImportError, Exception):
    LANGFUSE_AVAILABLE = False
    Langfuse = None  # type: ignore

logger = logging.getLogger(__name__)

# =============================================================================
# DATA MODELS
# =============================================================================


class IngestResult(BaseModel):
    """
    Result model for ingestion operation.

    Attributes:
        doc_id: Unique document identifier
        filename: Original PDF filename
        page_count: Number of pages processed
        chunk_count: Number of chunks created
        structured_kb_count: Number of structured KB objects inserted
        table_chunk_count: Number of table chunks detected
        indexed_chunk_count: Number of chunks successfully indexed
        uploaded_pdf_key: MinIO object key for uploaded PDF
        status: Overall ingestion status
        warnings: List of warnings encountered during ingestion
    """

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    filename: str
    page_count: int
    chunk_count: int
    structured_kb_count: int
    table_chunk_count: int
    indexed_chunk_count: int
    uploaded_pdf_key: str
    status: str
    warnings: list[str] = Field(default_factory=list)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def compute_doc_id(pdf_path: Path) -> str:
    """
    Compute a deterministic doc_id from the PDF file path.

    Uses SHA-256 hash of the absolute file path, truncated to 16 hex chars.

    Args:
        pdf_path: Path to the PDF file.

    Returns:
        Deterministic doc_id string.
    """
    abs_path = str(pdf_path.resolve())
    hash_digest = hashlib.sha256(abs_path.encode("utf-8")).hexdigest()
    return hash_digest[:16]


def compute_chunk_hash(chunk: ChunkResult) -> str:
    """
    Compute a deterministic hash for a chunk.

    Uses SHA-256 hash of the chunk content.

    Args:
        chunk: ChunkResult object.

    Returns:
        Chunk hash string.
    """
    content = chunk.content or ""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def infer_table_kb_type(content: str) -> str | None:
    """
    Infer the structured KB type from table content using simple heuristics.

    Args:
        content: Table content string.

    Returns:
        "root_cause_analysis", "cli_command_reference", or None if no match.
    """
    content_lower = content.lower()

    # Keywords for root cause analysis
    rca_keywords = {"symptom", "root cause", "fix", "severity"}
    rca_matches = sum(1 for kw in rca_keywords if kw in content_lower)

    # Keywords for CLI command reference
    cli_keywords = {"command", "syntax", "parameter", "example"}
    cli_matches = sum(1 for kw in cli_keywords if kw in content_lower)

    # Determine type based on keyword matches
    if rca_matches >= 2:
        return "root_cause_analysis"
    if cli_matches >= 2:
        return "cli_command_reference"

    return None


def _derive_tags_from_content(content: str) -> list[str]:
    """
    Derive simple tags from table content using keyword detection.

    Args:
        content: Table content string.

    Returns:
        List of derived tags.
    """
    content_lower = content.lower()
    tags = []

    # Extract common technical terms as tags
    if "error" in content_lower or "fail" in content_lower:
        tags.append("errors")
    if "config" in content_lower or "setting" in content_lower:
        tags.append("configuration")
    if "api" in content_lower:
        tags.append("api")
    if "database" in content_lower or "db" in content_lower:
        tags.append("database")
    if "server" in content_lower or "service" in content_lower:
        tags.append("infrastructure")

    return tags


def build_root_cause_object_from_table(
    chunk: ChunkResult,
    doc_id: str,
    filename: str,
) -> KnowledgeObject:
    """
    Build a RootCauseAnalysis KnowledgeObject from a table chunk.

    Args:
        chunk: ChunkResult with chunk_type="table"
        doc_id: Document identifier
        filename: Original PDF filename

    Returns:
        KnowledgeObject with RootCauseAnalysis data.
    """
    content = chunk.content or ""

    # Extract first line as potential title
    lines = content.split("\n")
    title = lines[0].strip() if lines else "Extracted Root Cause"

    # Derive tags from content
    tags = _derive_tags_from_content(content)

    # Create source reference
    source = Source(
        doc_id=doc_id,
        filename=filename,
        page_number=chunk.page_numbers[0] if chunk.page_numbers else None,
        section_path=chunk.section_path,
        chunk_id=chunk.id,
    )

    now = datetime.now(UTC)

    # Build RootCauseAnalysis with minimal valid data
    rca_data = RootCauseAnalysis(
        title=title,
        symptoms=["Extracted from table"],  # Placeholder
        severity="S3",  # Default severity
        root_cause=RootCauseDetail(
            summary="Extracted from table chunk",  # Placeholder
            affected_versions=[],
            fixed_in=[],
        ),
        fix=FixDetail(
            steps=["Refer to source document"],  # Placeholder
            cli_commands=[],
            config_params=[],
            estimated_time_minutes=None,
        ),
    )

    return KnowledgeObject(
        id=chunk.id,
        type="root_cause_analysis",
        version=1,
        sources=[source],
        created_at=now,
        updated_at=now,
        created_by="index_builder",
        chunk_hash=compute_chunk_hash(chunk),
        tags=tags,
        data=rca_data,
    )


def build_cli_command_object_from_table(
    chunk: ChunkResult,
    doc_id: str,
    filename: str,
) -> KnowledgeObject:
    """
    Build a CLICommandReference KnowledgeObject from a table chunk.

    Args:
        chunk: ChunkResult with chunk_type="table"
        doc_id: Document identifier
        filename: Original PDF filename

    Returns:
        KnowledgeObject with CLICommandReference data.
    """
    content = chunk.content or ""

    # Extract first non-empty line as potential command
    lines = [line.strip() for line in content.split("\n") if line.strip()]
    command = lines[0] if lines else "unknown"

    # Derive tags from content
    tags = _derive_tags_from_content(content)

    # Create source reference
    source = Source(
        doc_id=doc_id,
        filename=filename,
        page_number=chunk.page_numbers[0] if chunk.page_numbers else None,
        section_path=chunk.section_path,
        chunk_id=chunk.id,
    )

    now = datetime.now(UTC)

    # Build CLICommandReference with minimal valid data
    cli_data = CLICommandReference(
        command=command,
        syntax="Extracted from table",  # Placeholder
        parameters=[],  # Placeholder - would need LLM extraction
        examples=[],  # Placeholder
        related_commands=[],
        min_version=None,
    )

    return KnowledgeObject(
        id=chunk.id,
        type="cli_command_reference",
        version=1,
        sources=[source],
        created_at=now,
        updated_at=now,
        created_by="index_builder",
        chunk_hash=compute_chunk_hash(chunk),
        tags=tags,
        data=cli_data,
    )


def _upsert_document_metadata(
    doc_id: str,
    filename: str,
    page_count: int,
    chunk_count: int,
    minio_path: str,
) -> None:
    """
    Insert or update document metadata in PostgreSQL.

    Args:
        doc_id: Unique document identifier
        filename: Original PDF filename
        page_count: Number of pages in the PDF
        chunk_count: Number of chunks created
        minio_path: MinIO object key for the PDF
    """
    settings = get_settings()
    cfg = settings.database

    conninfo = (
        f"host={cfg.host} port={cfg.port} user={cfg.user} password={cfg.password} dbname={cfg.db}"
    )

    try:
        with psycopg.connect(conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO document_metadata (
                        doc_id, source_type, filename, page_count,
                        chunk_count, minio_path, version, ingested_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT (doc_id) DO UPDATE SET
                        filename = EXCLUDED.filename,
                        page_count = EXCLUDED.page_count,
                        chunk_count = EXCLUDED.chunk_count,
                        minio_path = EXCLUDED.minio_path,
                        version = document_metadata.version + 1,
                        ingested_at = EXCLUDED.ingested_at
                    """,
                    (
                        doc_id,
                        "pdf",
                        filename,
                        page_count,
                        chunk_count,
                        minio_path,
                        1,
                        datetime.now(UTC),
                    ),
                )
            conn.commit()

        logger.debug("Upserted document metadata for doc_id=%s", doc_id)

    except Exception as e:
        logger.error("Failed to upsert document metadata: %s", e)
        raise


def _log_langfuse_event(
    doc_id: str,
    filename: str,
    page_count: int,
    chunk_count: int,
    structured_kb_count: int,
    status: str,
) -> None:
    """
    Emit a LangFuse trace event for the ingestion.

    This function is non-fatal - if LangFuse fails, it logs a warning
    but does not fail the ingestion.

    Args:
        doc_id: Unique document identifier
        filename: Original PDF filename
        page_count: Number of pages in the PDF
        chunk_count: Number of chunks created
        structured_kb_count: Number of structured KB objects inserted
        status: Overall ingestion status
    """
    if not LANGFUSE_AVAILABLE:
        logger.debug("LangFuse not available, skipping trace event")
        return

    settings = get_settings()

    # Check if LangFuse is configured
    if not settings.langfuse.public_key or not settings.langfuse.secret_key:
        logger.debug("LangFuse not configured, skipping trace event")
        return

    try:
        langfuse = Langfuse(
            public_key=settings.langfuse.public_key,
            secret_key=settings.langfuse.secret_key,
            host=settings.langfuse.host,
        )

        # LangFuse v2 API
        langfuse.trace(
            name="pdf_ingestion",
            input={"doc_id": doc_id, "filename": filename},
            output={
                "page_count": page_count,
                "chunk_count": chunk_count,
                "structured_kb_count": structured_kb_count,
                "status": status,
            },
            metadata={
                "source": "index_builder",
                "ingestion_type": "pdf",
            },
        )

        logger.debug("Emitted LangFuse trace for doc_id=%s", doc_id)

    except Exception as e:
        logger.warning("Failed to emit LangFuse trace: %s", e)


# =============================================================================
# MAIN FUNCTION
# =============================================================================


def ingest_pdf(pdf_path: str | Path) -> IngestResult:
    """
    Ingest a PDF file into the RAG platform.

    This function coordinates the full ingestion flow:
    1. Process PDF into page-level extraction results
    2. Chunk those pages into retrieval chunks
    3. Index all chunks into BM25
    4. Extract selected table chunks into the structured KB using simple heuristics
    5. Upload the raw PDF to document storage
    6. Insert/update document metadata in PostgreSQL
    7. Emit a LangFuse trace/log event
    8. Return an IngestResult object with summary stats

    Args:
        pdf_path: Path to the PDF file (str or Path)

    Returns:
        IngestResult with summary statistics

    Raises:
        FileNotFoundError: If the PDF file does not exist
        ValueError: If the file is not a PDF
    """
    warnings: list[str] = []

    # =========================================================================
    # Step 1: Validate input
    # =========================================================================
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        logger.error("PDF file not found: %s", pdf_path)
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if pdf_path.suffix.lower() != ".pdf":
        logger.error("Invalid file type: %s", pdf_path.suffix)
        raise ValueError(f"File must be a PDF, got: {pdf_path.suffix}")

    filename = pdf_path.name
    logger.info("Starting ingestion for PDF: %s", filename)

    # =========================================================================
    # Step 2: Compute doc_id
    # =========================================================================
    doc_id = compute_doc_id(pdf_path)
    logger.debug("Computed doc_id: %s", doc_id)

    # =========================================================================
    # Step 3: Process PDF
    # =========================================================================
    logger.info("Processing PDF pages...")
    page_results: list[PageResult] = process_pdf(pdf_path)
    page_count = len(page_results)
    logger.info("Extracted %d pages from PDF", page_count)

    # =========================================================================
    # Step 4: Chunk pages
    # =========================================================================
    logger.info("Chunking pages...")
    chunks: list[ChunkResult] = chunk_pages(page_results, doc_id)
    chunk_count = len(chunks)
    logger.info("Created %d chunks from pages", chunk_count)

    # Count table chunks
    table_chunk_count = sum(1 for c in chunks if c.chunk_type == "table")

    # =========================================================================
    # Step 5: Initialize stores
    # =========================================================================
    logger.info("Initializing stores...")
    bm25_store = BM25Store()
    doc_store = DocStore()

    # =========================================================================
    # Step 6: Index chunks and extract structured KB
    # =========================================================================
    indexed_chunk_count = 0
    structured_kb_count = 0
    had_index_errors = False

    logger.info("Indexing chunks and extracting structured KB...")

    with StructuredKBStore() as structured_kb_store:
        for chunk in chunks:
            # Index into BM25 — skip structural heading chunks with no content
            if not chunk.content or not chunk.content.strip():
                logger.debug("Skipping empty/structural chunk %s (%r)", chunk.id, chunk.title)
                continue
            try:
                bm25_store.index_chunk(chunk, refresh=False)
                indexed_chunk_count += 1
            except Exception as e:
                warning_msg = f"Failed to index chunk {chunk.id}: {e}"
                logger.warning(warning_msg)
                warnings.append(warning_msg)
                had_index_errors = True

            # Attempt structured KB extraction for table chunks
            if chunk.chunk_type == "table":
                kb_type = infer_table_kb_type(chunk.content)

                if kb_type == "root_cause_analysis":
                    try:
                        kb_obj = build_root_cause_object_from_table(chunk, doc_id, filename)
                        structured_kb_store.insert(kb_obj)
                        structured_kb_count += 1
                        logger.debug("Inserted root_cause_analysis for chunk %s", chunk.id)
                    except Exception as e:
                        warning_msg = (
                            f"Failed to insert root_cause_analysis for chunk {chunk.id}: {e}"
                        )
                        logger.warning(warning_msg)
                        warnings.append(warning_msg)
                        had_index_errors = True

                elif kb_type == "cli_command_reference":
                    try:
                        kb_obj = build_cli_command_object_from_table(chunk, doc_id, filename)
                        structured_kb_store.insert(kb_obj)
                        structured_kb_count += 1
                        logger.debug("Inserted cli_command_reference for chunk %s", chunk.id)
                    except Exception as e:
                        warning_msg = (
                            f"Failed to insert cli_command_reference for chunk {chunk.id}: {e}"
                        )
                        logger.warning(warning_msg)
                        warnings.append(warning_msg)
                        had_index_errors = True
                else:
                    logger.debug("Table chunk %s did not match any KB type heuristics", chunk.id)

    # =========================================================================
    # Step 7: Upload raw PDF
    # =========================================================================
    logger.info("Uploading raw PDF to document store...")
    try:
        uploaded_pdf_key = doc_store.upload_pdf(pdf_path, doc_id)
        logger.info("Uploaded PDF with key: %s", uploaded_pdf_key)
    except Exception as e:
        logger.error("Failed to upload PDF: %s", e)
        raise

    # =========================================================================
    # Step 8: Write document metadata
    # =========================================================================
    logger.info("Writing document metadata...")
    try:
        _upsert_document_metadata(
            doc_id=doc_id,
            filename=filename,
            page_count=page_count,
            chunk_count=chunk_count,
            minio_path=uploaded_pdf_key,
        )
        logger.info("Document metadata written for doc_id=%s", doc_id)
    except Exception as e:
        logger.error("Failed to write document metadata: %s", e)
        raise

    # =========================================================================
    # Step 9: Emit LangFuse event
    # =========================================================================
    status = "partial" if had_index_errors else "success"
    _log_langfuse_event(
        doc_id=doc_id,
        filename=filename,
        page_count=page_count,
        chunk_count=chunk_count,
        structured_kb_count=structured_kb_count,
        status=status,
    )

    # =========================================================================
    # Step 10: Return result
    # =========================================================================
    logger.info(
        "Ingestion complete for %s: pages=%d, chunks=%d, indexed=%d, "
        "tables=%d, structured_kb=%d, status=%s",
        filename,
        page_count,
        chunk_count,
        indexed_chunk_count,
        table_chunk_count,
        structured_kb_count,
        status,
    )

    return IngestResult(
        doc_id=doc_id,
        filename=filename,
        page_count=page_count,
        chunk_count=chunk_count,
        structured_kb_count=structured_kb_count,
        table_chunk_count=table_chunk_count,
        indexed_chunk_count=indexed_chunk_count,
        uploaded_pdf_key=uploaded_pdf_key,
        status=status,
        warnings=warnings,
    )
