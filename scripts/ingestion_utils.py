#!/usr/bin/env python3
"""
Shared utilities for ingestion scripts.

This module provides common functions used across multiple ingestion scripts
to avoid code duplication.
"""

import hashlib
from pathlib import Path


def compute_doc_id(filepath: Path) -> str:
    """
    Compute unique document ID from file path.

    Uses MD5 hash of the file path to generate a deterministic, unique
    identifier for each document.

    Args:
        filepath: Path to the document file

    Returns:
        MD5 hash of the file path as a hexadecimal string

    Example:
        >>> from pathlib import Path
        >>> compute_doc_id(Path("/data/corpus/doc.pdf"))
        '5d41402abc4b2a76b9719d911017c592'
    """
    return hashlib.md5(str(filepath).encode()).hexdigest()


def chunk_text(text: str, chunk_size: int = 1024) -> list[str]:
    """
    Split text into chunks by grouping paragraphs.

    Splits text on double newlines (paragraphs), then groups paragraphs
    into chunks of approximately chunk_size characters. This preserves
    paragraph boundaries while keeping chunks reasonably sized.

    Args:
        text: The text content to chunk
        chunk_size: Target size for each chunk in characters (default: 1024)

    Returns:
        List of text chunks, each approximately chunk_size characters

    Example:
        >>> text = "Para 1.\\n\\nPara 2.\\n\\nPara 3."
        >>> chunks = chunk_text(text, chunk_size=50)
        >>> len(chunks)
        1
    """
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
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
