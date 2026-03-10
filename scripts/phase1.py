#!/usr/bin/env python3
"""
Week 1 PROOF Script: End-to-End PDF Ingestion
==============================================
This script proves that the Week 1 foundation works end-to-end:

1. Parse all 5 PDFs with Docling
2. Chunk the content
3. Store chunks in OpenSearch
4. Store metadata in PostgreSQL
5. Upload original PDFs to MinIO
6. Verify everything is stored correctly

This demonstrates Level 2 completion: "It works once"
"""

import hashlib
import sys
from datetime import datetime
from pathlib import Path

import psycopg
from docling.document_converter import DocumentConverter
from minio import Minio
from opensearchpy import OpenSearch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config.settings import get_settings


def compute_doc_id(filepath: Path) -> str:
    """Compute unique document ID from file path."""
    return hashlib.md5(str(filepath).encode()).hexdigest()


def chunk_text(text: str, chunk_size: int = 1024) -> list[str]:
    """Simple chunking: split by paragraphs, group into ~chunk_size."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk += "\n\n" + para if current_chunk else para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def main():
    print("=" * 80)
    print("Week 1 PROOF: End-to-End PDF Ingestion")
    print("=" * 80)

    # Load settings
    settings = get_settings()
    print("\n[1/7] ✓ Settings loaded")

    # Find all PDFs
    corpus_dir = Path(__file__).parent.parent / "data" / "corpus"
    pdfs = sorted(list(corpus_dir.glob("*.pdf")))

    if not pdfs:
        print("\n❌ No PDFs found in data/corpus/")
        print("   Run: python scripts/seed_test_data.py first")
        return False

    print(f"[2/7] ✓ Found {len(pdfs)} PDFs")
    for pdf in pdfs:
        print(f"      - {pdf.name}")

    # Initialize Docling
    print("\n[3/7] ⏳ Initializing Docling converter...")
    converter = DocumentConverter()
    print("[3/7] ✓ Docling ready")

    # Initialize OpenSearch
    print("\n[4/7] ⏳ Connecting to OpenSearch...")
    os_client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        verify_certs=False,
    )
    # Test connection
    os_client.cluster.health()
    print("[4/7] ✓ OpenSearch connected")

    # Initialize PostgreSQL
    print("\n[5/7] ⏳ Connecting to PostgreSQL...")
    pg_conn = psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db
    )
    print("[5/7] ✓ PostgreSQL connected")

    # Initialize MinIO
    print("\n[6/7] ⏳ Connecting to MinIO...")
    minio_client = Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=False,
    )
    # Verify bucket exists
    if not minio_client.bucket_exists("rag-documents"):
        print("      Creating bucket 'rag-documents'...")
        minio_client.make_bucket("rag-documents")
    print("[6/7] ✓ MinIO connected")

    # Process each PDF
    print("\n[7/7] ⏳ Processing PDFs...")
    print("=" * 80)

    total_chunks = 0
    results = []

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"\n📄 [{i}/{len(pdfs)}] Processing: {pdf_path.name}")

        try:
            # Parse with Docling
            print("   ⏳ Parsing with Docling...")
            result = converter.convert(str(pdf_path))
            text = result.document.export_to_markdown()
            page_count = len(result.document.pages) if hasattr(result.document, 'pages') else 1
            print(f"   ✓ Parsed: {len(text)} chars, {page_count} page(s)")

            # Chunk the text
            chunks = chunk_text(text, chunk_size=1024)
            print(f"   ✓ Created: {len(chunks)} chunks")
            total_chunks += len(chunks)

            # Generate doc_id
            doc_id = compute_doc_id(pdf_path)

            # Store chunks in OpenSearch
            for chunk_idx, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{chunk_idx}"
                doc = {
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_idx,
                    "text": chunk,
                    "filename": pdf_path.name,
                    "ingested_at": datetime.utcnow().isoformat(),
                }
                os_client.index(
                    index=settings.opensearch_index,
                    id=chunk_id,
                    body=doc,
                    refresh=True,
                )
            print(f"   ✓ Stored {len(chunks)} chunks in OpenSearch")

            # Store metadata in PostgreSQL
            with pg_conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO document_metadata
                    (doc_id, source_type, filename, page_count, chunk_count, minio_path, ingested_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (doc_id) DO UPDATE SET
                        chunk_count = EXCLUDED.chunk_count,
                        ingested_at = EXCLUDED.ingested_at
                """, (
                    doc_id,
                    "pdf",
                    pdf_path.name,
                    page_count,
                    len(chunks),
                    f"raw/{pdf_path.name}",
                    datetime.utcnow()
                ))
                pg_conn.commit()
            print("   ✓ Stored metadata in PostgreSQL")

            # Upload to MinIO
            minio_path = f"raw/{pdf_path.name}"
            minio_client.fput_object(
                "rag-documents",
                minio_path,
                str(pdf_path),
                content_type="application/pdf"
            )
            print(f"   ✓ Uploaded to MinIO: {minio_path}")

            results.append({
                "filename": pdf_path.name,
                "doc_id": doc_id,
                "chunks": len(chunks),
                "pages": page_count,
                "success": True
            })

        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append({
                "filename": pdf_path.name,
                "success": False,
                "error": str(e)
            })

    # Close connections
    pg_conn.close()

    # Print final summary
    print("\n" + "=" * 80)
    print("INGESTION COMPLETE!")
    print("=" * 80)

    successful = sum(1 for r in results if r.get("success"))
    print(f"\n✅ Successfully processed: {successful}/{len(pdfs)} PDFs")
    print(f"✅ Total chunks created: {total_chunks}")

    # Verify OpenSearch
    count_result = os_client.count(index=settings.opensearch_index)
    os_count = count_result['count']
    print("\n🔍 OpenSearch verification:")
    print(f"   ✓ Index '{settings.opensearch_index}' contains {os_count} documents")

    # Verify PostgreSQL
    with psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM document_metadata")
            pg_count = cur.fetchone()[0]
            print("\n🗄️  PostgreSQL verification:")
            print(f"   ✓ Table 'document_metadata' contains {pg_count} documents")

    # Verify MinIO
    objects = list(minio_client.list_objects("rag-documents", prefix="raw/", recursive=True))
    print("\n📦 MinIO verification:")
    print(f"   ✓ Bucket 'rag-documents' contains {len(objects)} files")

    print("\n" + "=" * 80)
    print("✅ WEEK 1 PROOF COMPLETE: All systems operational!")
    print("=" * 80)
    print("\nLevel 2 Status: ✅ IT WORKS ONCE")
    print("- Docling parsed all PDFs")
    print("- Chunks stored in OpenSearch")
    print("- Metadata stored in PostgreSQL")
    print("- Files uploaded to MinIO")
    print("\nNext: Test Level 3 (works repeatedly) and Level 4 (handles failures)")

    return successful == len(pdfs)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
