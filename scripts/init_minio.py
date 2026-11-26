#!/usr/bin/env python3
"""Initialize MinIO buckets for RAG platform."""

from minio import Minio
from minio.error import S3Error

from src.config.settings import get_settings


def create_buckets(client: Minio, bucket_names: list[str]) -> bool:
    """Create buckets if they don't exist."""
    try:
        for bucket_name in bucket_names:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                print(f"Created bucket: {bucket_name}")
            else:
                print(f"Bucket already exists: {bucket_name}")
        return True
    except S3Error as e:
        print(f"Error creating buckets: {e}")
        return False


def main():
    """Main function to connect to MinIO and create buckets."""
    # Get configuration from environment variables
    settings = get_settings()
    host = settings.minio_endpoint
    access_key = settings.minio_access_key
    secret_key = settings.minio_secret_key
    if not access_key or not secret_key:
        raise SystemExit("Set MINIO_ACCESS_KEY and MINIO_SECRET_KEY before initializing MinIO.")

    # Create client (secure=False for local HTTP)
    client = Minio(
        host,
        access_key=access_key,
        secret_key=secret_key,
        secure=False,
    )

    # List of buckets to create
    bucket_names = ["rag-documents", "rag-images"]

    # Create buckets
    if create_buckets(client, bucket_names):
        print("MinIO initialization completed successfully!")
    else:
        print("MinIO initialization failed!")
        exit(1)


if __name__ == "__main__":
    main()

