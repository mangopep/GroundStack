import shutil
import tempfile
from pathlib import Path

import fitz
import pytest

from src.ingestion.pdf_intelligence import process_pdf


@pytest.fixture(scope="module")
def test_data_dir():
    # Setup temporary directory for test PDFs
    temp_dir = Path(tempfile.mkdtemp(prefix="rag_test_pdfs_"))
    yield temp_dir
    # Teardown
    shutil.rmtree(temp_dir)


@pytest.fixture
def corrupted_pdf(test_data_dir):
    path = test_data_dir / "corrupted.pdf"
    path.write_bytes(b"This is not a valid PDF file. It is just some random bytes.")
    return path


@pytest.fixture
def large_pdf(test_data_dir):
    path = test_data_dir / "large.pdf"
    doc = fitz.open()
    # Create a 20-page document
    for i in range(20):
        page = doc.new_page()
        page.insert_text((50, 50), f"This is native text on page {i + 1}. " * 10)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture
def mixed_layout_pdf(test_data_dir):
    path = test_data_dir / "mixed.pdf"
    doc = fitz.open()

    # Page 1: Native text
    p1 = doc.new_page()
    p1.insert_text((50, 50), "This is a native page with enough text to be classified properly.")

    # Page 2: Scanned/Image (Not enough text)
    p2 = doc.new_page()
    p2.insert_text((50, 50), "Short")

    doc.save(path)
    doc.close()
    return path


def test_corrupted_pdf_handling(corrupted_pdf):
    # PyMuPDF should instantly throw FileDataError (which inherits from Exception in fitz)
    with pytest.raises(Exception) as exc_info:
        process_pdf(corrupted_pdf)
    assert "Failed to open file" in str(exc_info.value) or "FileDataError" in str(
        exc_info.value.__class__.__name__
    )


def test_large_pdf_extraction_status(large_pdf):
    # Docling versions may leave pages empty; those pages must report the
    # PyMuPDF fallback rather than claim primary-parser success.
    results = process_pdf(large_pdf)

    assert len(results) == 20
    for res in results:
        assert res.page_type == "native"
        assert res.extraction_status in {"success", "partial_fallback"}
        assert len(res.text) > 0


def test_mixed_layout_status_tracking(mixed_layout_pdf, monkeypatch):
    # First verify standard extraction
    results = process_pdf(mixed_layout_pdf)

    assert len(results) == 2
    # Page 1 should be native success
    assert results[0].page_type == "native"
    assert results[0].extraction_status == "success"

    # Page 2 should be scanned and marked as skipped (since we have no OCR yet)
    assert results[1].page_type == "scanned"
    assert results[1].extraction_status == "skipped"
    assert results[1].text == ""

    # Now let's simulate Docling failing on the native page to force a fallback
    def mock_export(*args, **kwargs):
        raise ValueError("Simulated Docling failure")

    # We need to monkeypatch the actual DoclingDocument class being used inside pdf_intelligence
    # But since it's hard to catch the specific instance dynamically inside process_pdf,
    # A cleaner integration test for fallback is to intercept the export logic

    class MockConverter:
        def convert(self, path):
            class MockDoc:
                def export_to_markdown(self, page_no):
                    raise ValueError("Simulated internal Docling crash")

            class MockResult:
                document = MockDoc()

            return MockResult()

    from src.ingestion import pdf_intelligence as pdf_mod

    monkeypatch.setattr(pdf_mod, "_get_converter", lambda: MockConverter())

    results = process_pdf(mixed_layout_pdf)

    # Page 1 should now be partial_fallback because Docling failed but PyMuPDF succeeded
    assert results[0].page_type == "native"
    assert results[0].extraction_status == "partial_fallback"
    assert len(results[0].text) > 0  # Text should still exist via PyMuPDF get_text()
    assert "native page with enough text" in results[0].text
