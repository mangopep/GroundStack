#!/usr/bin/env python3
"""Seed test data script for RAG platform.

Creates 5 sample PDFs of different types.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Configuration
DATA_DIR = Path(__file__).parent.parent / "data"
CORPUS_DIR = DATA_DIR / "corpus"


def create_handbook_doc(output_path):
    """Create a handbook-style document with headings."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("System Administration Handbook", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    sections = [
        ("1. Getting Started", "Welcome to the system administration guide."),
        ("2. User Management", "Users can be added using the admin console."),
        ("3. Backup Procedures", "Daily backups run at 2 AM UTC."),
        ("4. Monitoring", "Monitor system health using the metrics dashboard."),
        ("5. Troubleshooting", "Check logs in data/logs/ for details."),
    ]

    for heading, content in sections:
        story.append(Paragraph(heading, styles["Heading1"]))
        story.append(Paragraph(content, styles["Normal"]))
        story.append(Spacer(1, 0.2 * inch))

    doc.build(story)
    print(f"Created: {output_path.name}")


def create_table_doc(output_path):
    """Create a document with tables."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Configuration Parameters Reference", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    data = [
        ["Parameter", "Type", "Default", "Description"],
        ["max_connections", "int", "100", "Maximum database connections"],
        ["cache_size", "mb", "512", "Redis cache size"],
        ["chunk_size", "int", "1024", "Text chunk size"],
        ["embedding_model", "str", "bge-base", "Embedding model"],
    ]
    t = Table(data, colWidths=[1.5 * inch, 0.8 * inch, 0.8 * inch, 2.2 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(t)
    doc.build(story)
    print(f"Created: {output_path.name}")


def create_cli_output_doc(output_path):
    """Create a document with CLI output."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    mono_style = ParagraphStyle('Mono', parent=styles['Normal'], fontName='Courier', fontSize=9)
    story = []

    story.append(Paragraph("CLI Command Reference", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    cmd = "$ docker compose up -d<br/>$ docker compose ps<br/>$ make backup"
    story.append(Paragraph(cmd, mono_style))
    doc.build(story)
    print(f"Created: {output_path.name}")


def create_multicolumn_doc(output_path):
    """Create a multi-column document."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Technical Architecture Overview", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    data = [
        ["Component", "Technology"],
        ["Database", "PostgreSQL + AGE"],
        ["Search", "OpenSearch 2.17"],
        ["Cache", "Redis 7.4"],
        ["Storage", "MinIO (S3)"],
    ]
    t = Table(data, colWidths=[2.5 * inch, 2.5 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.darkgreen),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(t)
    doc.build(story)
    print(f"Created: {output_path.name}")


def create_scanned_doc(output_path):
    """Create a document simulating a scanned PDF."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Emergency Procedures Quick Reference", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    content = """
    <b>Database Recovery:</b><br/>
    1. Stop services: make stop<br/>
    2. Restore volume<br/>
    3. Run: docker compose up -d<br/><br/>

    <b>Search Index Rebuild:</b><br/>
    python scripts/init_opensearch.py<br/><br/>

    <b>MinIO Console:</b><br/>
    http://localhost:9001
    """
    story.append(Paragraph(content, styles["Normal"]))
    doc.build(story)
    print(f"Created: {output_path.name}")


def create_rca_and_cli_doc(output_path):
    """Create a document with RCA and CLI reference tables (triggers structured KB extraction)."""
    doc = SimpleDocTemplate(str(output_path), pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Runbook: Root Cause Analysis & CLI Reference", styles["Title"]))
    story.append(Spacer(1, 0.3 * inch))

    # ── RCA table ── keywords: symptom, root cause, fix, severity
    story.append(Paragraph("Root Cause Analysis", styles["Heading1"]))
    story.append(Spacer(1, 0.1 * inch))
    rca_data = [
        ["Symptom", "Root Cause", "Fix", "Severity"],
        ["Search returns no results", "OpenSearch index empty", "Run reindex_all.py", "High"],
        ["Slow ingest", "Docling CPU-bound", "Increase worker threads", "Medium"],
        ["LangFuse traces missing", "SDK/server version mismatch", "Pin langfuse>=2,<3", "Low"],
    ]
    rca_table = Table(rca_data, colWidths=[1.5 * inch, 1.7 * inch, 1.7 * inch, 0.9 * inch])
    rca_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkred),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(rca_table)
    story.append(Spacer(1, 0.3 * inch))

    # ── CLI table ── keywords: command, syntax, parameter, example
    story.append(Paragraph("CLI Command Reference", styles["Heading1"]))
    story.append(Spacer(1, 0.1 * inch))
    cli_data = [
        ["Command", "Syntax", "Parameter", "Example"],
        ["ingest", "python phase1.py ingest <file>", "--path PATH", "python phase1.py ingest data/"],
        ["search", "python test_search.py <query>", "--top-k N", "python test_search.py 'TCP'"],
        ["reindex", "python reindex_all.py", "--force", "python reindex_all.py --force"],
    ]
    cli_table = Table(cli_data, colWidths=[0.8 * inch, 2.0 * inch, 1.2 * inch, 1.8 * inch])
    cli_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(cli_table)
    doc.build(story)
    print(f"Created: {output_path.name}")


def main():
    print("=" * 50)
    print("RAG Platform - Seed Test Data")
    print("=" * 50)

    CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    pdfs_to_create = [
        ("01_handbook.pdf", create_handbook_doc),
        ("02_tables.pdf", create_table_doc),
        ("03_cli_commands.pdf", create_cli_output_doc),
        ("04_multicolumn.pdf", create_multicolumn_doc),
        ("05_scanned_reference.pdf", create_scanned_doc),
        ("06_rca_and_cli.pdf", create_rca_and_cli_doc),
    ]

    print("\n=== Creating sample PDFs ===")
    for filename, creator_func in pdfs_to_create:
        output_path = CORPUS_DIR / filename
        try:
            creator_func(output_path)
        except Exception as e:
            print(f"Error creating {filename}: {e}")

    # List created files
    pdfs = list(CORPUS_DIR.glob("*.pdf"))
    print(f"\n=== Created {len(pdfs)} PDF files ===")
    for p in pdfs:
        print(f"  - {p.name}")


if __name__ == "__main__":
    main()
