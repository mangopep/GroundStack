"""
PDF Intelligence Module for RAG Ingestion Pipeline.

This module handles PDF page-level classification and text extraction.

Week 2: Page classification uses PyMuPDF; native text extraction uses Docling.
Week 5: Surya OCR for scanned pages will be added.
"""

import logging
from pathlib import Path
from typing import Literal

import fitz  # PyMuPDF
from docling.document_converter import DocumentConverter
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

load_dotenv()

# =============================================================================
# LOGGING
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# DATA MODELS
# =============================================================================


class PageResult(BaseModel):
    """
    Result model for a single PDF page extraction.

    Attributes:
        page_num: Page number (1-indexed)
        text: Extracted text content
        page_type: Classification as "native" or "scanned"
        extraction_status: Status of text extraction:
                           - "success": Cleanly extracted by primary method (Docling)
                           - "partial_fallback": Primary method failed, fell back to raw PyMuPDF
                           - "failed": Extraction completely failed or yielded no usable text
                           - "skipped": Extraction deferred or skipped (e.g., scanned pages without OCR)
        tables: List of extracted tables (placeholder for future)
        images: List of extracted images (placeholder for future)

    Design note — heading detection
    --------------------------------
    ``PageResult`` intentionally does **not** carry a ``heading`` field.
    Heading detection runs during the chunking stage (``chunk_pages()``) using
    PyMuPDF font-size span heuristics applied to the page text.  The detected
    headings surface as ``ChunkResult.title`` and ``ChunkResult.section_path``
    on the downstream chunks — not on individual pages.
    """

    model_config = ConfigDict(extra="forbid")

    page_num: int
    text: str
    page_type: Literal["native", "scanned"]
    extraction_status: Literal["success", "partial_fallback", "failed", "skipped"] = "success"
    tables: list[str] = Field(default_factory=list)
    images: list[str] = Field(default_factory=list)

    @field_validator("page_num")
    @classmethod
    def validate_page_num(cls, v: int) -> int:
        if v < 1:
            raise ValueError("page_num must be >= 1")
        return v


# =============================================================================
# PAGE CLASSIFICATION
# =============================================================================


def classify_page(page: fitz.Page) -> Literal["native", "scanned"]:
    """
    Classify a PDF page as native (text-based) or scanned (image-based).

    Args:
        page: PyMuPDF page object

    Returns:
        "native" if extracted text length > 50 characters, otherwise "scanned"
    """
    text = page.get_text()
    if len(text.strip()) > 50:
        return "native"
    return "scanned"


# =============================================================================
# TEXT EXTRACTION
# =============================================================================

_docling_converter: DocumentConverter | None = None


def _get_converter() -> DocumentConverter:
    """Lazily initialise the Docling converter (one instance per process)."""
    global _docling_converter
    if _docling_converter is None:
        _docling_converter = DocumentConverter()
    return _docling_converter


# =============================================================================
# PDF PROCESSING
# =============================================================================


def process_pdf(pdf_path: str | Path) -> list[PageResult]:
    """
    Process a PDF file and extract text from each page.

    Args:
        pdf_path: Path to the PDF file (str or Path)

    Returns:
        List of PageResult objects for each page

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file is not a PDF

    Week 2: Page classification uses PyMuPDF; native text extraction uses Docling.
    Week 5: Surya OCR for scanned pages will be added.
    """
    pdf_path = Path(pdf_path)

    # Validate file exists
    if not pdf_path.exists():
        logger.error(f"File not found: {pdf_path}")
        raise FileNotFoundError(f"File not found: {pdf_path}")

    # Validate file extension
    if pdf_path.suffix.lower() != ".pdf":
        logger.error(f"Invalid file type: {pdf_path.suffix}")
        raise ValueError(f"File must be a PDF, got: {pdf_path.suffix}")

    logger.info(f"Starting PDF processing: {pdf_path}")

    # Open PDF document with guaranteed cleanup on any exception
    doc = fitz.open(pdf_path)
    try:
        num_pages = len(doc)
        logger.info(f"PDF has {num_pages} pages")

        results: list[PageResult] = []
        classifications: dict[int, Literal["native", "scanned"]] = {}
        has_native = False

        # Phase 1: Classify all pages using PyMuPDF
        for page_num in range(num_pages):
            page = doc[page_num]
            actual_page_num = page_num + 1  # 1-indexed

            # Classify page using PyMuPDF text heuristic
            page_type = classify_page(page)
            classifications[actual_page_num] = page_type
            if page_type == "native":
                has_native = True

        dl_doc = None
        docling_failed = False
        if has_native:
            # Phase 2: Parse full document with Docling once
            logger.info("Native pages found. Parsing full document with Docling...")
            try:
                converter = _get_converter()
                dl_result = converter.convert(str(pdf_path))
                dl_doc = dl_result.document
            except Exception:
                logger.exception(
                    "Docling full conversion failed. Falling back to PyMuPDF for all native pages."
                )
                docling_failed = True

        # Phase 3: Construct results
        for actual_page_num in range(1, num_pages + 1):
            page_type = classifications[actual_page_num]
            logger.debug(f"Page {actual_page_num}: classified as {page_type}")

            if page_type == "native":
                # Extract page-specific text from the Docling document
                text = ""
                status: Literal["success", "partial_fallback", "failed", "skipped"] = "success"

                if dl_doc:
                    try:
                        text = dl_doc.export_to_markdown(page_no=actual_page_num).strip()
                    except Exception:
                        logger.exception("Failed to extract markdown for page %d", actual_page_num)

                # Fallback: if Docling returns empty text but PyMuPDF classified it as native
                if not text:
                    if not docling_failed:
                        logger.warning(
                            f"Page {actual_page_num}: Docling extracted empty text for native page. "
                            "Falling back to PyMuPDF raw text."
                        )
                    else:
                        logger.debug(
                            f"Page {actual_page_num}: using PyMuPDF fallback (Docling unavailable)"
                        )
                    pymupdf_page = doc[actual_page_num - 1]
                    text = pymupdf_page.get_text().strip()
                    status = "partial_fallback" if text else "failed"

                result = PageResult(
                    page_num=actual_page_num,
                    text=text,
                    page_type=page_type,
                    extraction_status=status,
                    tables=[],  # Placeholders for future extraction
                    images=[],
                )
            else:
                # Scanned page - return empty text (OCR will be added in Week 5)
                logger.debug(f"Page {actual_page_num}: scanned page, OCR pending (Week 5)")
                result = PageResult(
                    page_num=actual_page_num,
                    text="",
                    page_type=page_type,
                    extraction_status="skipped",  # Mark skipped since we can't extract yet
                    tables=[],
                    images=[],
                )

            results.append(result)
            logger.info(
                f"Page {actual_page_num}/{num_pages}: {page_type} (text length: {len(result.text)})"
            )
    finally:
        doc.close()

    logger.info(
        f"PDF processing complete: {len(results)} pages processed, "
        f"native={sum(1 for r in results if r.page_type == 'native')}, "
        f"scanned={sum(1 for r in results if r.page_type == 'scanned')}"
    )

    # Log summary of extraction statuses
    status_counts = {
        "success": sum(1 for r in results if r.extraction_status == "success"),
        "partial_fallback": sum(1 for r in results if r.extraction_status == "partial_fallback"),
        "failed": sum(1 for r in results if r.extraction_status == "failed"),
        "skipped": sum(1 for r in results if r.extraction_status == "skipped"),
    }
    logger.info(
        f"Extraction status summary: success={status_counts['success']}, "
        f"partial_fallback={status_counts['partial_fallback']}, "
        f"failed={status_counts['failed']}, skipped={status_counts['skipped']}"
    )

    return results
