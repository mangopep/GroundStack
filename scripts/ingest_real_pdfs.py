#!/usr/bin/env python3
"""
Ingest Real PDFs - Full Pipeline Test
======================================
This script runs the COMPLETE ingestion pipeline on real technical documentation
and stores everything in OpenSearch, PostgreSQL, and MinIO.

This is the ultimate Week 1 validation - proving the system works with production data.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from docling.document_converter import DocumentConverter
from minio import Minio
from opensearchpy import OpenSearch

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ingestion_utils import chunk_text, compute_doc_id
from src.config.settings import get_settings


def main() -> bool:
    """
    Main ingestion pipeline for real technical PDFs.

    Performs end-to-end ingestion:
    1. Finds all PDFs in data/corpus/real_docs/
    2. Parses each with Docling
    3. Chunks the extracted text
    4. Stores chunks in OpenSearch (full-text search)
    5. Stores metadata in PostgreSQL
    6. Uploads original PDFs to MinIO
    7. Verifies all data storage

    Returns:
        True if all PDFs were successfully processed, False otherwise
    """
    print("=" * 80)
    print("Real PDF Ingestion - Full Pipeline")
    print("=" * 80)
    print("\nIngesting REAL technical documentation into the RAG system")

    # Load settings
    settings = get_settings()
    print("\n[1/7] ✓ Settings loaded")

    # Find real PDFs
    real_corpus = Path(__file__).parent.parent / "data" / "corpus" / "real_docs"
    pdfs = sorted([p for p in real_corpus.glob("*.pdf")])

    if not pdfs:
        print(f"\n❌ No PDFs found in: {real_corpus}")
        print("   Run: python scripts/test_real_pdfs.py first")
        return False

    print(f"[2/7] ✓ Found {len(pdfs)} real PDFs")
    for pdf in pdfs:
        file_size = pdf.stat().st_size / 1024
        print(f"      - {pdf.name} ({file_size:.1f} KB)")

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
    if not minio_client.bucket_exists("rag-documents"):
        print("      Creating bucket 'rag-documents'...")
        minio_client.make_bucket("rag-documents")
    print("[6/7] ✓ MinIO connected")

    # Process each PDF
    print("\n[7/7] ⏳ Processing real PDFs...")
    print("=" * 80)

    total_pages = 0
    total_chunks = 0
    results = []

    for i, pdf_path in enumerate(pdfs, 1):
        print(f"\n📄 [{i}/{len(pdfs)}] Processing: {pdf_path.name}")
        file_size = pdf_path.stat().st_size / 1024
        print(f"   File size: {file_size:.1f} KB")

        try:
            # Parse with Docling
            print("   ⏳ Parsing with Docling...")
            result = converter.convert(str(pdf_path))
            text = result.document.export_to_markdown()
            page_count = len(result.document.pages) if hasattr(result.document, 'pages') else 1
            print(f"   ✓ Parsed: {len(text):,} chars, {page_count} page(s)")

            # Chunk the text
            chunks = chunk_text(text, chunk_size=1024)
            print(f"   ✓ Created: {len(chunks)} chunks")
            total_pages += page_count
            total_chunks += len(chunks)

            # Generate doc_id
            doc_id = compute_doc_id(pdf_path)

            # Store chunks in OpenSearch
            print("   ⏳ Storing chunks in OpenSearch...")
            for chunk_idx, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{chunk_idx}"
                doc = {
                    "doc_id": doc_id,
                    "chunk_id": chunk_id,
                    "chunk_index": chunk_idx,
                    "text": chunk,
                    "filename": pdf_path.name,
                    "ingested_at": datetime.now(UTC).isoformat(),
                }
                os_client.index(
                    index=settings.opensearch_index,
                    id=chunk_id,
                    body=doc,
                    refresh=True,
                )
            print(f"   ✓ Stored {len(chunks)} chunks in OpenSearch")

            # Store metadata in PostgreSQL
            print("   ⏳ Storing metadata in PostgreSQL...")
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
                    f"real_docs/{pdf_path.name}",
                    datetime.now(UTC)
                ))
                pg_conn.commit()
            print("   ✓ Stored metadata in PostgreSQL")

            # Upload to MinIO
            print("   ⏳ Uploading to MinIO...")
            minio_path = f"real_docs/{pdf_path.name}"
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
                "chars": len(text),
                "success": True
            })

            print(f"   ✅ Complete! ({page_count} pages → {len(chunks)} chunks)")

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
    print("REAL PDF INGESTION COMPLETE!")
    print("=" * 80)

    successful = [r for r in results if r.get("success")]
    print(f"\n✅ Successfully processed: {len(successful)}/{len(pdfs)} PDFs")
    print(f"✅ Total pages: {total_pages}")
    print(f"✅ Total chunks created: {total_chunks}")

    if successful:
        total_chars = sum(r["chars"] for r in successful)
        print(f"✅ Total characters: {total_chars:,}")
        print(f"✅ Average chunks per page: {total_chunks / total_pages:.1f}")

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

            # Show real vs test PDFs
            cur.execute("""
                SELECT
                    CASE WHEN minio_path LIKE 'real_docs/%' THEN 'Real' ELSE 'Test' END as type,
                    COUNT(*) as count,
                    SUM(page_count) as total_pages,
                    SUM(chunk_count) as total_chunks
                FROM document_metadata
                GROUP BY type
            """)
            print("\n   Document breakdown:")
            for row in cur.fetchall():
                doc_type, count, pages, chunks = row
                print(f"      {doc_type} PDFs: {count} files, {pages} pages, {chunks} chunks")

    # Verify MinIO
    objects = list(minio_client.list_objects("rag-documents", recursive=True))
    print("\n📦 MinIO verification:")
    print(f"   ✓ Bucket 'rag-documents' contains {len(objects)} files")

    print("\n" + "=" * 80)
    print("✅ PRODUCTION DATA TEST COMPLETE!")
    print("=" * 80)
    print(f"\n🎉 Week 1 system successfully processed {len(successful)} real technical documents")
    print(f"🎉 Total: {total_pages} pages, {total_chunks} chunks")
    print("\n✅ Ready for Week 2: Query pipeline and FastAPI")

    return len(successful) == len(pdfs)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
