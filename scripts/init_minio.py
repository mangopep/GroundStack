#!/usr/bin/env python3
"""Initialize MinIO buckets for RAG platform."""

import os

from minio import Minio
from minio.error import S3Error


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
    host = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")

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

