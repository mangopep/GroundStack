"""Unit tests for DocStore.

All MinIO I/O is mocked — no server required.

Run with:
    pytest tests/unit/test_doc_store.py -v
"""

import io
from pathlib import Path
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from minio.error import S3Error

from src.stores.doc_store import DocStore, DEFAULT_DOCUMENTS_BUCKET, DEFAULT_IMAGES_BUCKET, DEFAULT_URL_EXPIRY_SECONDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store() -> DocStore:
    """Return a DocStore whose Minio client is fully mocked (no server needed)."""
    mock_client = MagicMock()
    mock_client.bucket_exists.return_value = True
    store = DocStore.__new__(DocStore)
    store._endpoint = "localhost:9000"
    store._access_key = "minioadmin"
    store._secret_key = "minioadmin"
    store._secure = False
    store._documents_bucket = DEFAULT_DOCUMENTS_BUCKET
    store._images_bucket = DEFAULT_IMAGES_BUCKET
    store._client = mock_client
    return store


# ---------------------------------------------------------------------------
# 1. Initialisation
# ---------------------------------------------------------------------------

class TestInit:
    @patch("src.stores.doc_store.Minio")
    def test_init_defaults(self, mock_minio):
        """Minio is constructed with localhost:9000 when no env vars are set."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_client

        store = DocStore()

        mock_minio.assert_called_once_with(
            "localhost:9000",
            access_key="minioadmin",
            secret_key="minioadmin",
            secure=False,
        )
        assert store._documents_bucket == DEFAULT_DOCUMENTS_BUCKET
        assert store._images_bucket == DEFAULT_IMAGES_BUCKET

    @patch("src.stores.doc_store.Minio")
    def test_init_reads_env_vars(self, mock_minio):
        """Constructor picks up MINIO_* env vars."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_client

        env = {
            "MINIO_ENDPOINT": "minio.prod:9000",
            "MINIO_ACCESS_KEY": "prod_key",
            "MINIO_SECRET_KEY": "prod_secret",
            "MINIO_SECURE": "true",
            "MINIO_DOCUMENTS_BUCKET": "my-docs",
            "MINIO_IMAGES_BUCKET": "my-images",
        }
        with patch.dict("os.environ", env):
            store = DocStore()

        assert store._endpoint == "minio.prod:9000"
        assert store._documents_bucket == "my-docs"
        assert store._images_bucket == "my-images"
        assert store._secure is True

    @patch("src.stores.doc_store.Minio")
    def test_init_creates_missing_buckets(self, mock_minio):
        """Buckets that don't exist are created on init."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = False
        mock_minio.return_value = mock_client

        DocStore()

        assert mock_client.make_bucket.call_count == 2

    @patch("src.stores.doc_store.Minio")
    def test_init_skips_existing_buckets(self, mock_minio):
        """No make_bucket call when buckets already exist."""
        mock_client = MagicMock()
        mock_client.bucket_exists.return_value = True
        mock_minio.return_value = mock_client

        DocStore()

        mock_client.make_bucket.assert_not_called()


# ---------------------------------------------------------------------------
# 2. upload_pdf
# ---------------------------------------------------------------------------

class TestUploadPdf:
    def test_upload_pdf_calls_fput_object(self, tmp_path):
        """fput_object is called with correct bucket, key, and content-type."""
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF fake content")

        store = _make_store()
        result = store.upload_pdf(pdf, "doc1")

        store._client.fput_object.assert_called_once_with(
            DEFAULT_DOCUMENTS_BUCKET,
            "doc1",
            str(pdf),
            content_type="application/pdf",
        )
        assert result == "doc1"

    def test_upload_pdf_rejects_non_pdf(self, tmp_path):
        """ValueError is raised for files that are not .pdf."""
        txt = tmp_path / "notes.txt"
        txt.write_bytes(b"not a pdf")

        store = _make_store()

        with pytest.raises(ValueError, match="PDF"):
            store.upload_pdf(txt, "doc2")

    def test_upload_pdf_missing_file(self, tmp_path):
        """FileNotFoundError is raised when the file does not exist."""
        store = _make_store()

        with pytest.raises(FileNotFoundError):
            store.upload_pdf(tmp_path / "ghost.pdf", "doc3")

    def test_upload_pdf_empty_doc_id(self, tmp_path):
        """ValueError is raised when doc_id is blank."""
        pdf = tmp_path / "a.pdf"
        pdf.write_bytes(b"%PDF")

        store = _make_store()

        with pytest.raises(ValueError, match="doc_id"):
            store.upload_pdf(pdf, "   ")

    def test_upload_pdf_accepts_string_path(self, tmp_path):
        """upload_pdf also accepts a plain string for file_path."""
        pdf = tmp_path / "doc.pdf"
        pdf.write_bytes(b"%PDF")

        store = _make_store()
        result = store.upload_pdf(str(pdf), "doc-str")

        store._client.fput_object.assert_called_once()
        assert result == "doc-str"

    def test_upload_pdf_propagates_s3_error(self, tmp_path):
        """S3Error from fput_object is re-raised."""
        pdf = tmp_path / "err.pdf"
        pdf.write_bytes(b"%PDF")

        store = _make_store()
        store._client.fput_object.side_effect = S3Error(
            "InternalError", "simulated", "req", "host", "err", "resp"
        )

        with pytest.raises(S3Error):
            store.upload_pdf(pdf, "doc-err")


# ---------------------------------------------------------------------------
# 3. upload_image
# ---------------------------------------------------------------------------

class TestUploadImage:
    def test_upload_image_calls_put_object(self):
        """put_object is called with correct bucket, key, and content-type."""
        store = _make_store()
        result = store.upload_image(b"\x89PNG\r\n", "img1")

        args, kwargs = store._client.put_object.call_args
        assert args[0] == DEFAULT_IMAGES_BUCKET
        assert args[1] == "img1"
        assert isinstance(args[2], io.BytesIO)
        assert kwargs["length"] == 6
        assert kwargs["content_type"] == "image/png"
        assert result == "img1"

    def test_upload_image_custom_content_type(self):
        """Custom content_type is forwarded to put_object."""
        store = _make_store()
        store.upload_image(b"\xff\xd8\xff", "img2", content_type="image/jpeg")

        _, kwargs = store._client.put_object.call_args
        assert kwargs["content_type"] == "image/jpeg"

    def test_upload_image_rejects_empty_bytes(self):
        """ValueError is raised when image_bytes is empty."""
        store = _make_store()

        with pytest.raises(ValueError, match="image_bytes"):
            store.upload_image(b"", "img3")

    def test_upload_image_rejects_empty_id(self):
        """ValueError is raised when image_id is blank."""
        store = _make_store()

        with pytest.raises(ValueError, match="image_id"):
            store.upload_image(b"\x89PNG", "")

    def test_upload_image_propagates_s3_error(self):
        """S3Error from put_object is re-raised."""
        store = _make_store()
        store._client.put_object.side_effect = S3Error(
            "InternalError", "simulated", "req", "host", "err", "resp"
        )

        with pytest.raises(S3Error):
            store.upload_image(b"\x89PNG", "img-err")


# ---------------------------------------------------------------------------
# 4. get_pdf_url
# ---------------------------------------------------------------------------

class TestGetPdfUrl:
    def test_get_pdf_url_calls_presigned(self):
        """presigned_get_object is called with correct bucket, key, and expiry."""
        store = _make_store()
        store._client.presigned_get_object.return_value = "http://minio/doc1?token=abc"

        url = store.get_pdf_url("doc1")

        store._client.presigned_get_object.assert_called_once_with(
            DEFAULT_DOCUMENTS_BUCKET,
            "doc1",
            expires=timedelta(seconds=DEFAULT_URL_EXPIRY_SECONDS),
        )
        assert url == "http://minio/doc1?token=abc"

    def test_get_pdf_url_custom_expiry(self):
        """Custom expiry_seconds is forwarded correctly."""
        store = _make_store()
        store._client.presigned_get_object.return_value = "http://minio/doc1?x=y"

        store.get_pdf_url("doc1", expiry_seconds=120)

        _, kwargs = store._client.presigned_get_object.call_args
        assert kwargs["expires"] == timedelta(seconds=120)

    def test_get_pdf_url_rejects_empty_doc_id(self):
        """ValueError is raised when doc_id is blank."""
        store = _make_store()

        with pytest.raises(ValueError, match="doc_id"):
            store.get_pdf_url("  ")

    def test_get_pdf_url_propagates_s3_error(self):
        """S3Error from presigned_get_object is re-raised."""
        store = _make_store()
        store._client.presigned_get_object.side_effect = S3Error(
            "NoSuchKey", "key not found", "req", "host", "err", "resp"
        )

        with pytest.raises(S3Error):
            store.get_pdf_url("missing-doc")


# ---------------------------------------------------------------------------
# 5. list_docs
# ---------------------------------------------------------------------------

class TestListDocs:
    def test_list_docs_returns_object_names(self):
        """list_objects results are unpacked into a plain list of strings."""
        store = _make_store()

        obj_a, obj_b = MagicMock(), MagicMock()
        obj_a.object_name = "doc-alpha"
        obj_b.object_name = "doc-beta"
        store._client.list_objects.return_value = iter([obj_a, obj_b])

        docs = store.list_docs()

        store._client.list_objects.assert_called_once_with(
            DEFAULT_DOCUMENTS_BUCKET, recursive=True
        )
        assert docs == ["doc-alpha", "doc-beta"]

    def test_list_docs_empty_bucket(self):
        """Empty bucket returns an empty list."""
        store = _make_store()
        store._client.list_objects.return_value = iter([])

        assert store.list_docs() == []

    def test_list_docs_propagates_s3_error(self):
        """S3Error from list_objects is re-raised."""
        store = _make_store()
        store._client.list_objects.side_effect = S3Error(
            "AccessDenied", "denied", "req", "host", "err", "resp"
        )

        with pytest.raises(S3Error):
            store.list_docs()


# ---------------------------------------------------------------------------
# 6. _normalize_secure_flag
# ---------------------------------------------------------------------------

class TestNormalizeSecureFlag:
    def setup_method(self):
        self.store = DocStore.__new__(DocStore)

    def test_explicit_true(self):
        assert self.store._normalize_secure_flag(True) is True

    def test_explicit_false(self):
        assert self.store._normalize_secure_flag(False) is False

    def test_string_true_variants(self):
        for v in ("true", "True", "TRUE", "1", "yes"):
            assert self.store._normalize_secure_flag(v) is True

    def test_string_false_variants(self):
        for v in ("false", "0", "no", ""):
            assert self.store._normalize_secure_flag(v) is False

    def test_none_falls_back_to_env(self):
        with patch.dict("os.environ", {"MINIO_SECURE": "true"}):
            assert self.store._normalize_secure_flag(None) is True

    def test_none_defaults_to_false_when_no_env(self):
        with patch.dict("os.environ", {}, clear=True):
            assert self.store._normalize_secure_flag(None) is False
