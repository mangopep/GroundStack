"""
Integration tests for DocStore.

Runs against a real MinIO instance.  Skipped automatically when MinIO is
not reachable (e.g. in CI without docker-compose).

Start MinIO then run:
    docker-compose up -d minio
    pytest tests/integration/test_doc_store_minio.py -v
"""

import os
import uuid
from pathlib import Path

import pytest
from minio import Minio

from src.stores.doc_store import DocStore

# ---------------------------------------------------------------------------
# Reachability guard
# ---------------------------------------------------------------------------


def _minio_reachable() -> bool:
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "")
    try:
        client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=False)
        client.list_buckets()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    os.environ.get("GROUNDSTACK_RUN_SERVICE_INTEGRATION") != "1" or not _minio_reachable(),
    reason="Set GROUNDSTACK_RUN_SERVICE_INTEGRATION=1 with a disposable MinIO service",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _uid(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def store():
    """Use per-test buckets so this suite cannot see or alter user objects."""
    suffix = uuid.uuid4().hex
    documents_bucket = f"gs-test-docs-{suffix}"
    images_bucket = f"gs-test-images-{suffix}"
    result = DocStore(documents_bucket=documents_bucket, images_bucket=images_bucket)
    yield result
    for bucket in (documents_bucket, images_bucket):
        for obj in result._client.list_objects(bucket, recursive=True):
            result._client.remove_object(bucket, obj.object_name)
        result._client.remove_bucket(bucket)


@pytest.fixture
def sample_pdf(tmp_path) -> Path:
    pdf = tmp_path / f"{_uid('doc')}.pdf"
    # Minimal valid-looking PDF header; sufficient for upload/download proof.
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF")
    return pdf


# ---------------------------------------------------------------------------
# 1. PDF upload → list → presigned URL
# ---------------------------------------------------------------------------


class TestPdfRoundTrip:
    def test_upload_pdf_appears_in_list(self, store, sample_pdf):
        doc_id = _uid("pdf")
        store.upload_pdf(sample_pdf, doc_id)

        docs = store.list_docs()
        assert doc_id in docs

    def test_presigned_url_is_http(self, store, sample_pdf):
        doc_id = _uid("pdf-url")
        store.upload_pdf(sample_pdf, doc_id)

        url = store.get_pdf_url(doc_id)
        assert url.startswith("http"), f"Expected http URL, got: {url}"

    def test_presigned_url_contains_doc_id(self, store, sample_pdf):
        doc_id = _uid("pdf-key")
        store.upload_pdf(sample_pdf, doc_id)

        url = store.get_pdf_url(doc_id)
        assert doc_id in url

    def test_upload_pdf_idempotent(self, store, sample_pdf):
        """Uploading the same doc_id twice does not raise."""
        doc_id = _uid("pdf-idem")
        store.upload_pdf(sample_pdf, doc_id)
        store.upload_pdf(sample_pdf, doc_id)  # overwrite — should not raise

        assert doc_id in store.list_docs()


# ---------------------------------------------------------------------------
# 2. Image upload
# ---------------------------------------------------------------------------


class TestImageUpload:
    def test_upload_image_png(self, store):
        image_id = _uid("img-png")
        # Minimal 1×1 white PNG bytes
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00"
            b"\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00"
            b"\x00\x00\x00IEND\xaeB`\x82"
        )
        result = store.upload_image(png_bytes, image_id)
        assert result == image_id

    def test_upload_image_jpeg(self, store):
        image_id = _uid("img-jpg")
        # Minimal JPEG header marker
        jpeg_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 20 + b"\xff\xd9"
        result = store.upload_image(jpeg_bytes, image_id, content_type="image/jpeg")
        assert result == image_id


# ---------------------------------------------------------------------------
# 3. list_docs
# ---------------------------------------------------------------------------


class TestListDocs:
    def test_list_docs_returns_list(self, store):
        docs = store.list_docs()
        assert isinstance(docs, list)

    def test_list_docs_includes_newly_uploaded(self, store, sample_pdf):
        doc_id = _uid("list-proof")
        store.upload_pdf(sample_pdf, doc_id)

        docs = store.list_docs()
        assert doc_id in docs


# ---------------------------------------------------------------------------
# 4. Validation still enforced against real server
# ---------------------------------------------------------------------------


class TestValidationLive:
    def test_upload_pdf_rejects_non_pdf(self, store, tmp_path):
        txt = tmp_path / "notes.txt"
        txt.write_bytes(b"plain text")

        with pytest.raises(ValueError, match="PDF"):
            store.upload_pdf(txt, _uid("bad"))

    def test_upload_pdf_missing_file_raises(self, store, tmp_path):
        with pytest.raises(FileNotFoundError):
            store.upload_pdf(tmp_path / "ghost.pdf", _uid("ghost"))

    def test_upload_image_empty_bytes_raises(self, store):
        with pytest.raises(ValueError, match="image_bytes"):
            store.upload_image(b"", _uid("empty-img"))

    def test_get_pdf_url_empty_doc_id_raises(self, store):
        with pytest.raises(ValueError, match="doc_id"):
            store.get_pdf_url("")
