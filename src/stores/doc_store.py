"""MinIO-backed document store wrapper for RAG platform."""

import io
import logging
import os
from pathlib import Path
from datetime import timedelta

from minio import Minio
from minio.error import S3Error

logger = logging.getLogger(__name__)

DEFAULT_DOCUMENTS_BUCKET = "rag-documents"
DEFAULT_IMAGES_BUCKET = "rag-images"
DEFAULT_URL_EXPIRY_SECONDS = 3600  # 1 hour


class DocStore:
    """MinIO-backed document store for PDFs and images."""

    def __init__(
        self,
        endpoint: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        secure: bool | None = None,
        documents_bucket: str | None = None,
        images_bucket: str | None = None,
    ) -> None:
        """
        Initialize the document store.

        Args:
            endpoint: MinIO endpoint (defaults to MINIO_ENDPOINT env var).
            access_key: MinIO access key (defaults to MINIO_ACCESS_KEY env var).
            secret_key: MinIO secret key (defaults to MINIO_SECRET_KEY env var).
            secure: Use HTTPS (defaults to MINIO_SECURE env var).
            documents_bucket: Documents bucket name (defaults to MINIO_DOCUMENTS_BUCKET).
            images_bucket: Images bucket name (defaults to MINIO_IMAGES_BUCKET).
        """
        self._endpoint = endpoint or os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self._access_key = access_key or os.getenv("MINIO_ACCESS_KEY", "")
        self._secret_key = secret_key or os.getenv("MINIO_SECRET_KEY", "")
        self._secure = self._normalize_secure_flag(secure)
        self._documents_bucket = documents_bucket or os.getenv(
            "MINIO_DOCUMENTS_BUCKET", DEFAULT_DOCUMENTS_BUCKET
        )
        self._images_bucket = images_bucket or os.getenv(
            "MINIO_IMAGES_BUCKET", DEFAULT_IMAGES_BUCKET
        )

        logger.info(
            "Initializing DocStore with endpoint=%s, documents_bucket=%s, images_bucket=%s",
            self._endpoint,
            self._documents_bucket,
            self._images_bucket,
        )

        self._client = Minio(
            self._endpoint,
            access_key=self._access_key,
            secret_key=self._secret_key,
            secure=self._secure,
        )

        self._ensure_bucket_exists(self._documents_bucket)
        self._ensure_bucket_exists(self._images_bucket)
        self._verify_connection()

    def _normalize_secure_flag(self, value: str | bool | None) -> bool:
        """Normalize the secure flag to a boolean."""
        if value is None:
            # Fall back to environment variable if not provided
            env_value = os.getenv("MINIO_SECURE")
            if env_value is not None:
                return env_value.lower() in ("true", "1", "yes")
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return False

    def _ensure_bucket_exists(self, bucket_name: str) -> None:
        """Create bucket if it doesn't exist."""
        try:
            if not self._client.bucket_exists(bucket_name):
                self._client.make_bucket(bucket_name)
                logger.info("Created bucket: %s", bucket_name)
            else:
                logger.debug("Bucket already exists: %s", bucket_name)
        except S3Error as e:
            logger.error("Failed to ensure bucket exists: %s", e)
            raise

    def _verify_connection(self) -> None:
        """Verify MinIO connection by listing buckets."""
        try:
            self._client.list_buckets()
            logger.info("Successfully connected to MinIO")
        except S3Error as e:
            logger.error("Failed to connect to MinIO: %s", e)
            raise

    def upload_pdf(self, file_path: str | Path, doc_id: str) -> str:
        """
        Upload a PDF file to the documents bucket.

        Args:
            file_path: Path to the PDF file.
            doc_id: Unique identifier for the document (used as object key).

        Returns:
            The stored object key.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file is not a PDF or doc_id is empty.
        """
        path = Path(file_path)

        if not path.exists():
            logger.error("PDF file not found: %s", path)
            raise FileNotFoundError(f"PDF file not found: {path}")

        if not path.suffix.lower() == ".pdf":
            logger.error("Invalid file extension: %s", path.suffix)
            raise ValueError(f"File must be a PDF, got: {path.suffix}")

        if not doc_id or not doc_id.strip():
            logger.error("Empty doc_id provided")
            raise ValueError("doc_id cannot be empty")

        try:
            self._client.fput_object(
                self._documents_bucket,
                doc_id,
                str(path),
                content_type="application/pdf",
            )
            logger.info("Uploaded PDF: %s to bucket %s", doc_id, self._documents_bucket)
            return doc_id
        except S3Error as e:
            logger.error("Failed to upload PDF: %s", e)
            raise

    def upload_image(
        self,
        image_bytes: bytes,
        image_id: str,
        content_type: str = "image/png",
    ) -> str:
        """
        Upload image bytes to the images bucket.

        Args:
            image_bytes: Raw image content.
            image_id: Unique identifier for the image (used as object key).
            content_type: MIME type of the image (default: image/png).

        Returns:
            The stored object key.

        Raises:
            ValueError: If image_bytes is empty or image_id is empty.
        """
        if not image_bytes:
            logger.error("Empty image bytes provided")
            raise ValueError("image_bytes cannot be empty")

        if not image_id or not image_id.strip():
            logger.error("Empty image_id provided")
            raise ValueError("image_id cannot be empty")

        try:
            data = io.BytesIO(image_bytes)
            data_len = len(image_bytes)
            self._client.put_object(
                self._images_bucket,
                image_id,
                data,
                length=data_len,
                content_type=content_type,
            )
            logger.info(
                "Uploaded image: %s to bucket %s", image_id, self._images_bucket
            )
            return image_id
        except S3Error as e:
            logger.error("Failed to upload image: %s", e)
            raise

    def get_pdf_url(
        self, doc_id: str, expiry_seconds: int = DEFAULT_URL_EXPIRY_SECONDS
    ) -> str:
        """
        Generate a presigned URL for a PDF document.

        Args:
            doc_id: The document ID.
            expiry_seconds: URL expiration time in seconds (default: 1 hour).

        Returns:
            The presigned URL string.

        Raises:
            ValueError: If doc_id is empty.
        """
        if not doc_id or not doc_id.strip():
            logger.error("Empty doc_id provided for URL generation")
            raise ValueError("doc_id cannot be empty")

        try:
            url = self._client.presigned_get_object(
                self._documents_bucket,
                doc_id,
                expires=timedelta(seconds=expiry_seconds),
            )
            logger.debug("Generated presigned URL for: %s", doc_id)
            return url
        except S3Error as e:
            logger.error("Failed to generate presigned URL: %s", e)
            raise

    def list_docs(self) -> list[str]:
        """
        List all document keys in the documents bucket.

        Returns:
            List of object keys (strings).
        """
        try:
            objects = self._client.list_objects(
                self._documents_bucket,
                recursive=True,
            )
            return [obj.object_name for obj in objects]
        except S3Error as e:
            logger.error("Failed to list documents: %s", e)
            raise

