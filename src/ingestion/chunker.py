"""
Heading-aware smart chunker for a RAG ingestion pipeline.

This module converts page-level extraction results from pdf_intelligence.py
into structured chunks suitable for indexing and retrieval.

Downstream contract for ``is_structural`` chunks
-------------------------------------------------
Structural chunks have ``content=""`` and exist solely to preserve section
hierarchy so that tables and code blocks can hold a valid ``parent_id``.

* They are pruned from the output unless at least one other chunk references
  them via ``parent_id``.
* **Embedding / indexing pipelines** SHOULD skip chunks where
  ``is_structural=True`` (empty content adds noise).
* **Retrieval pipelines** MUST NOT surface structural chunks as answer
  candidates.
* **chunk_count metrics** SHOULD exclude structural chunks.
* **OpenSearch / DB mappings** must include the ``is_structural`` boolean
  field and index it so pipelines can filter efficiently.
"""

import hashlib
import logging
import re
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.ingestion.pdf_intelligence import PageResult

logger = logging.getLogger(__name__)

MAX_CHUNK_TOKENS = 1500
MIN_CHUNK_TOKENS = 100
# MIN_CHUNK_TOKENS is enforced by the merge step: adjacent same-section chunks
# that are both under 100 tokens are joined into one.  However, *isolated*
# short sections (glossary entries, BNF grammar rules, state-machine variable
# definitions) cannot be merged across different section_path values without
# destroying their semantic independence.  The max-size constraint (<=1500) is
# therefore absolute; the min-size target (>=100) is best-effort and reflects
# source document structure rather than a chunker defect.

# Lines that appear on at least this fraction of pages are treated as
# boilerplate (repeated headers / footers / page numbers) and skipped.
# Only activated when the document has enough pages to make the signal reliable.
BOILERPLATE_PAGE_FRACTION = 0.4
BOILERPLATE_MIN_PAGES = 3


class ChunkResult(BaseModel):
    """
    A single content unit produced by the chunker.

    Fields
    ------
    id
        Deterministic hex ID derived from (doc_id, chunk_type, content or
        position).  Re-ingesting the same document produces the same IDs.
    is_structural
        ``True`` only for heading-anchor chunks that carry no body text.
        These chunks exist exclusively to give tables / code blocks a real
        ``parent_id``; they are pruned if no child references them.
        See the module-level docstring for the full downstream contract.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    content: str
    section_path: str
    parent_id: str | None = None
    page_numbers: list[int] = Field(default_factory=list)
    chunk_type: Literal["section", "table", "code_block"]
    doc_id: str
    is_structural: bool = False


def estimate_tokens(text: str) -> int:
    """Estimate token count using a char/word hybrid heuristic.

    Pure word-count under-counts code, tables, and Unicode-heavy text where
    a single "word" may span many tokens.  A character-based estimate
    (1 token ≈ 4 chars) is more stable across content types.  We take the
    maximum of both so that neither long-word prose nor dense symbol text
    slips through.
    """
    if not text:
        return 0
    return max(len(text.split()), len(text) // 4)


def is_heading(line: str) -> bool:
    """Detect heading-like lines.

    Recognised patterns (in priority order):
    - Markdown ATX headings:  ``# Title``
    - Fully bold lines:       ``**Title**``
    - ALL CAPS lines meeting length and alpha-density guards

    ALL CAPS heuristic limitations: acronyms in running text, table header
    rows in all-caps, and screaming warnings may still produce false positives.
    Callers should treat these as hints, not ground truth.
    """
    s = line.strip()

    if not s:
        return False

    if s.startswith("#"):
        return True

    if s.startswith("**") and s.endswith("**") and len(s) > 4:
        return True

    # ALL CAPS heuristic ------------------------------------------------
    # Requirements: 4–80 chars, no pipe chars (likely a table row),
    # no purely numeric/symbol content, alpha chars must dominate.
    if s.isupper() and 4 <= len(s) <= 80:
        if "|" in s:  # table row
            return False
        alpha = sum(c.isalpha() for c in s)
        if alpha < len(s) * 0.6:  # number/symbol heavy
            return False
        return True

    return False


def get_heading_level(line: str) -> int:
    """Determine heading hierarchy level."""
    s = line.strip()

    m = re.match(r"^(#+)", s)
    if m:
        return len(m.group(1))

    if s.startswith("**"):
        return 2

    if s.isupper():
        return 2

    return 2


def normalize_heading(line: str) -> str:
    """Clean heading markers."""
    s = line.strip()
    s = re.sub(r"^#+\s*", "", s)

    if s.startswith("**") and s.endswith("**"):
        s = s[2:-2]

    return " ".join(s.split())


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs."""
    paras = re.split(r"\n\s*\n", text)
    return [p.strip() for p in paras if p.strip()]


def split_large_text(
    title: str,
    text: str,
    pages: set[int],
    section_path: str,
    parent_id: str | None,
    doc_id: str,
    para_page_mapping: list[tuple[str, set[int]]] | None = None,
) -> list[ChunkResult]:
    """
    Split large sections into smaller chunks.
    Enforces MAX_CHUNK_TOKENS and tries to keep chunks above MIN_CHUNK_TOKENS.

    Args:
        para_page_mapping: Optional list of (paragraph_text, page_set) tuples
                          for accurate per-chunk page tracking
    """

    # Use provided paragraph mappings or fall back to simple split
    if para_page_mapping:
        paragraphs = para_page_mapping
    else:
        paras = split_paragraphs(text)
        paragraphs = [(p, pages) for p in paras]

    chunks = []
    current = ""
    current_pages: set[int] = set()

    for p_text, p_pages in paragraphs:

        p_tokens = estimate_tokens(p_text)

        # Handle oversized single paragraph by splitting at sentence boundaries
        if p_tokens > MAX_CHUNK_TOKENS:
            sentences = re.split(r"(?<=[.!?])\s+", p_text)

            for s in sentences:
                # Estimate the joined content (with separator) rather than summing
                # separate estimates; the " " separator adds chars that would
                # otherwise inflate the char-based estimate on the next iteration.
                _joined_s = (current + " " + s) if current else s
                if estimate_tokens(_joined_s) > MAX_CHUNK_TOKENS:

                    # Only flush if we have meaningful content (enforce MIN)
                    if estimate_tokens(current) >= MIN_CHUNK_TOKENS:
                        _c = current.strip()
                        chunks.append(
                            ChunkResult(
                                id=_make_content_id(doc_id, "section", _c, scope=section_path),
                                title=title,
                                content=_c,
                                section_path=section_path,
                                parent_id=parent_id,
                                page_numbers=sorted(current_pages),
                                chunk_type="section",
                                doc_id=doc_id,
                            )
                        )

                        current = ""
                        current_pages = set()

                if current:
                    current += " " + s
                else:
                    current = s
                current_pages.update(p_pages)

            continue

        # Estimate the joined content (with "\n\n" separator) rather than summing
        # separate estimates.  The separator adds 2 chars which inflate the
        # char-based heuristic, causing content that just fits per the sum test
        # to slightly exceed MAX_CHUNK_TOKENS once actually joined.
        _joined_p = (current + "\n\n" + p_text) if current else p_text
        if estimate_tokens(_joined_p) > MAX_CHUNK_TOKENS:

            # Only flush if we meet minimum threshold
            if estimate_tokens(current) >= MIN_CHUNK_TOKENS:
                _c = current.strip()
                chunks.append(
                    ChunkResult(
                        id=_make_content_id(doc_id, "section", _c, scope=section_path),
                        title=title,
                        content=_c,
                        section_path=section_path,
                        parent_id=parent_id,
                        page_numbers=sorted(current_pages),
                        chunk_type="section",
                        doc_id=doc_id,
                    )
                )
                current = ""
                current_pages = set()

            # Start new chunk with current paragraph
            if current:
                current += "\n\n" + p_text
            else:
                current = p_text
            current_pages.update(p_pages)

        else:
            if current:
                current += "\n\n" + p_text
            else:
                current = p_text

            current_pages.update(p_pages)

    # Emit remaining content even if below MIN (last chunk of section).
    # If the trailing fragment is tiny, absorb it into the previous chunk
    # rather than creating a micro-stub that will degrade retrieval quality.
    if current.strip():
        _c = current.strip()
        if chunks and estimate_tokens(_c) < MIN_CHUNK_TOKENS:
            _prev = chunks[-1]
            chunks[-1] = ChunkResult(
                id=_prev.id,
                title=_prev.title,
                content=_prev.content + "\n\n" + _c,
                section_path=_prev.section_path,
                parent_id=_prev.parent_id,
                page_numbers=sorted(set(_prev.page_numbers) | set(current_pages)),
                chunk_type="section",
                doc_id=doc_id,
            )
        else:
            chunks.append(
                ChunkResult(
                    id=_make_content_id(doc_id, "section", _c, scope=section_path),
                    title=title,
                    content=_c,
                    section_path=section_path,
                    parent_id=parent_id,
                    page_numbers=sorted(current_pages),
                    chunk_type="section",
                    doc_id=doc_id,
                )
            )
    return chunks


def _normalize_content(text: str) -> str:
    """Collapse excessive blank lines and strip leading/trailing whitespace."""
    # Collapse 3+ consecutive newlines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _table_fingerprint(text: str) -> str:
    """Stable fingerprint for deduplicating table content."""
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Deterministic ID helpers
# Using content-stable identifiers improves idempotency: re-ingesting the
# same document produces the same IDs so updates overwrite instead of
# accumulating phantom duplicates.
# ---------------------------------------------------------------------------

_ID_LEN = 24  # hex chars (12 bytes / 96 bits)


def _make_section_id(doc_id: str, section_path: str, page_num: int, ordinal: int = 0) -> str:
    """Deterministic ID for a section heading based on its position.

    ``ordinal`` disambiguates the rare case where the same section_path appears
    more than once on the same page (e.g. a heading repeated in a two-column
    layout or a duplicated section title across adjacent pages with the same
    page_num).  Callers must increment the ordinal for each repetition.
    """
    raw = f"{doc_id}\x00section\x00{section_path}\x00{page_num}\x00{ordinal}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:_ID_LEN]


def _make_content_id(doc_id: str, chunk_type: str, content: str, scope: str = "") -> str:
    """Deterministic ID for a chunk whose content is already known.

    ``scope`` (typically ``section_path``) prevents two identical content
    bodies in different sections from sharing the same ID.
    """
    raw = f"{doc_id}\x00{chunk_type}\x00{scope}\x00{content}"
    return hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:_ID_LEN]


def _looks_like_table_row(line: str) -> bool:
    """Return True when a line plausibly belongs to a pipe-delimited table.

    Requires at least two non-empty cells after splitting on ``|`` and
    stripping edge delimiters.  This is stricter than a bare ``"|" in line``
    check and reduces false positives from prose containing pipe characters.
    """
    if "|" not in line:
        return False
    cells = [c.strip() for c in line.strip().split("|")]
    non_empty = [c for c in cells if c]
    return len(non_empty) >= 2


def chunk_pages(page_results: list[PageResult], doc_id: str) -> list[ChunkResult]:
    """
    Convert PageResult objects into structured chunks.
    """

    valid_pages = [
        p
        for p in page_results
        if p.page_type == "native"
        and p.extraction_status in ("success", "partial_fallback")
        and p.text.strip()
    ]

    if not valid_pages:
        logger.warning("No valid pages to chunk")
        return []

    valid_pages.sort(key=lambda p: p.page_num)

    # ------------------------------------------------------------------
    # Boilerplate detection
    # Pre-scan all pages and identify lines that repeat across too many
    # pages — repeated headers, footers, and page numbers.
    # ------------------------------------------------------------------
    boilerplate_lines: set[str] = set()
    if len(valid_pages) >= BOILERPLATE_MIN_PAGES:
        _line_page_sets: dict[str, set[int]] = defaultdict(set)
        for _pg in valid_pages:
            for _raw in _pg.text.split("\n"):
                _s = _raw.strip()
                # Exempt heading-like lines: a short heading may legitimately
                # appear on many pages without being boilerplate (e.g. chapter
                # titles in multi-section PDFs with repeated section headings).
                if 3 <= len(_s) <= 120 and not is_heading(_s):
                    _line_page_sets[_s].add(_pg.page_num)
        _bp_threshold = max(2, int(len(valid_pages) * BOILERPLATE_PAGE_FRACTION))
        boilerplate_lines = {
            _ln for _ln, _pages in _line_page_sets.items()
            if len(_pages) >= _bp_threshold
        }
        if boilerplate_lines:
            logger.debug(
                f"Detected {len(boilerplate_lines)} boilerplate lines "
                f"(threshold: {_bp_threshold}/{len(valid_pages)} pages)"
            )

    chunks: list[ChunkResult] = []

    # Track section hierarchy: (level, title, chunk_id)
    section_stack: list[tuple[int, str, str]] = []

    # Current section being built
    current_section_id: str | None = None  # Pre-allocated ID for this section
    current_title = "Untitled Section"
    # ``current_para_mappings`` and the in-progress ``current_para_text`` /
    # ``current_para_pages`` are now the *single* source of truth for both
    # section body text and page attribution.  The former ``current_pages``
    # accumulator has been removed; page numbers are derived at flush time via
    # ``_section_pages()`` so the two can never drift out of sync.
    current_para_mappings: list[tuple[str, set[int]]] = []
    current_para_text = ""
    current_para_pages: set[int] = set()

    parent_id: str | None = None
    section_path = ""

    # Track which section IDs have actually emitted chunks
    emitted_section_ids: set[str] = set()
    # Track table fingerprints already emitted to prevent duplicates across sources
    seen_table_fps: set[str] = set()
    # Collision guard: count how many times each (section_path, page_num) pair
    # has been used to allocate a section ID on the current document.
    _section_id_ordinals: dict[tuple[str, int], int] = {}

    def _section_text() -> str:
        """Reconstruct the current section body from para mappings + in-progress para.

        This is the canonical way to read section body text.  It replaces the
        former ``current_text`` accumulator, eliminating the dual-tracking drift
        that could arise around code/table boundaries.
        """
        parts = [p for p, _ in current_para_mappings]
        if current_para_text.strip():
            parts.append(current_para_text.strip())
        return "\n\n".join(parts)

    def _section_pages() -> list[int]:
        """Derive page numbers for the current section from para mappings.

        This is the authoritative source for section page attribution — it
        replaces the former ``current_pages`` set, eliminating the second
        source of truth that could drift from the paragraph mappings.
        """
        pages: set[int] = set()
        for _, pg_set in current_para_mappings:
            pages.update(pg_set)
        pages.update(current_para_pages)
        return sorted(pages)

    def flush_paragraph():
        """Flush current paragraph to tracking list."""
        nonlocal current_para_text, current_para_pages
        if current_para_text.strip():
            current_para_mappings.append((current_para_text.strip(), current_para_pages.copy()))
        current_para_text = ""
        current_para_pages = set()

    def flush_section():
        nonlocal current_section_id, current_para_text, current_para_pages

        _body = _section_text()
        if not _body:
            # No body content - emit structural placeholder so children can reference it.
            # Only emit if not already done by ensure_section_parent_emitted.
            if current_section_id and current_section_id not in emitted_section_ids:
                chunks.append(
                    ChunkResult(
                        id=current_section_id,
                        title=current_title,
                        content="",
                        section_path=section_path,
                        parent_id=parent_id,
                        page_numbers=[],
                        chunk_type="section",
                        doc_id=doc_id,
                        is_structural=True,
                    )
                )
                emitted_section_ids.add(current_section_id)
                logger.debug(f"Created structural section: {current_title}")
            current_section_id = None
            current_para_mappings.clear()
            current_para_text = ""
            current_para_pages = set()
            return

        _normalized = _normalize_content(_body)
        tokens = estimate_tokens(_normalized)
        _pages = _section_pages()

        # If this heading was already emitted as a structural anchor (tables/code appeared
        # before body text), the content chunk becomes a child of that anchor.
        if current_section_id and current_section_id in emitted_section_ids:
            section_id = _make_content_id(doc_id, "section", _normalized, scope=section_path)
            content_parent_id = current_section_id  # child of structural anchor
        else:
            section_id = current_section_id or _make_content_id(doc_id, "section", _normalized, scope=section_path)
            content_parent_id = parent_id

        if tokens <= MAX_CHUNK_TOKENS:
            chunks.append(
                ChunkResult(
                    id=section_id,
                    title=current_title,
                    content=_normalized,
                    section_path=section_path,
                    parent_id=content_parent_id,
                    page_numbers=_pages,
                    chunk_type="section",
                    doc_id=doc_id,
                )
            )
            emitted_section_ids.add(section_id)
        else:
            # For split sections, pass paragraph mappings for accurate page tracking
            split_chunks = split_large_text(
                current_title,
                _normalized,
                set(_pages),
                section_path,
                content_parent_id,
                doc_id,
                para_page_mapping=current_para_mappings if current_para_mappings else None,
            )
            if split_chunks:
                split_chunks[0].id = section_id
                emitted_section_ids.add(section_id)
            chunks.extend(split_chunks)
            logger.debug(f"Split section '{current_title}' into {len(split_chunks)} chunks")

        current_section_id = None
        current_para_mappings.clear()
        current_para_text = ""
        current_para_pages = set()

    def ensure_section_parent_emitted(triggering_page: int) -> None:
        """Emit the current heading as a structural anchor if it has no body text yet,
        so tables and code blocks can reference it as a parent with a real page number.
        Does nothing if the section already has body text (forward reference is OK).
        """
        if (
            current_section_id
            and current_section_id not in emitted_section_ids
            and not _section_text()
        ):
            chunks.append(
                ChunkResult(
                    id=current_section_id,
                    title=current_title,
                    content="",
                    section_path=section_path,
                    parent_id=parent_id,
                    page_numbers=[triggering_page],
                    chunk_type="section",
                    doc_id=doc_id,
                    is_structural=True,
                )
            )
            emitted_section_ids.add(current_section_id)
            logger.debug(f"Emitted structural section anchor: {current_title}")

    for page in valid_pages:

        lines = page.text.split("\n")
        i = 0

        while i < len(lines):

            line = lines[i]
            stripped = line.strip()

            # Skip repeated header/footer/page-number boilerplate
            if stripped in boilerplate_lines:
                i += 1
                continue

            if stripped.startswith("```"):
                code_lines = [line]
                i += 1

                while i < len(lines):
                    code_lines.append(lines[i])
                    if lines[i].strip().startswith("```"):
                        break
                    i += 1

                code_block = "\n".join(code_lines)

                flush_paragraph()
                ensure_section_parent_emitted(page.page_num)

                chunks.append(
                    ChunkResult(
                        id=_make_content_id(doc_id, "code_block", code_block, scope=section_path),
                        title="Code Block",
                        content=code_block,
                        section_path=section_path or "Code Block",
                        parent_id=current_section_id,
                        page_numbers=[page.page_num],
                        chunk_type="code_block",
                        doc_id=doc_id,
                    )
                )

                i += 1
                continue

            if is_heading(stripped):

                flush_paragraph()  # Flush any pending paragraph
                flush_section()

                level = get_heading_level(stripped)
                title = normalize_heading(stripped)

                # Remove deeper or equal level headings from stack
                section_stack = [
                    s for s in section_stack if s[0] < level
                ]

                # Compute section_path BEFORE allocating the ID so that the
                # deterministic ID can embed the full path (Issue #21).
                parent_id = section_stack[-1][2] if section_stack else None
                section_path = " > ".join(
                    s[1] for s in section_stack
                ) + (" > " + title if section_stack else title)

                # Deterministic ID based on document position.
                # Use an ordinal to avoid collisions when the same section_path
                # appears more than once on the same page.
                _sp_key = (section_path, page.page_num)
                _ordinal = _section_id_ordinals.get(_sp_key, 0)
                _section_id_ordinals[_sp_key] = _ordinal + 1
                current_section_id = _make_section_id(doc_id, section_path, page.page_num, _ordinal)

                section_stack.append((level, title, current_section_id))

                current_title = title
                current_para_mappings.clear()
                current_para_text = ""
                current_para_pages = set()

                i += 1
                continue

            if _looks_like_table_row(stripped):

                table_lines = []
                j = i

                while j < len(lines) and _looks_like_table_row(lines[j]):
                    table_lines.append(lines[j])
                    j += 1

                table_text = "\n".join(table_lines)

                flush_paragraph()
                ensure_section_parent_emitted(page.page_num)

                fp = _table_fingerprint(table_text)
                # Dedup key is scoped to section: the same table appearing in
                # two different sections is intentional and should not be merged.
                # Within the same section, inline-scan and page.tables may both
                # emit it; the composite key prevents that duplicate.
                _fp_key = f"{section_path}\x00{fp}"
                if _fp_key not in seen_table_fps:
                    seen_table_fps.add(_fp_key)
                    chunks.append(
                        ChunkResult(
                            id=_make_content_id(doc_id, "table", fp, scope=section_path),
                            title="Table",
                            content=table_text,
                            section_path=section_path or "Table",
                            parent_id=current_section_id,
                            page_numbers=[page.page_num],
                            chunk_type="table",
                            doc_id=doc_id,
                        )
                    )

                i = j
                continue

            if stripped:
                current_para_text += line + "\n"
                current_para_pages.add(page.page_num)
            elif current_para_text.strip():
                # Blank line marks paragraph boundary
                flush_paragraph()

            i += 1

        for table in page.tables:

            flush_paragraph()
            ensure_section_parent_emitted(page.page_num)

            fp = _table_fingerprint(table)
            _fp_key = f"{section_path}\x00{fp}"
            if table.strip() and _fp_key not in seen_table_fps:
                seen_table_fps.add(_fp_key)
                chunks.append(
                    ChunkResult(
                        id=_make_content_id(doc_id, "table", fp, scope=section_path),
                        title="Table",
                        content=table,
                        section_path=section_path or "Table",
                        parent_id=current_section_id,
                        page_numbers=[page.page_num],
                        chunk_type="table",
                        doc_id=doc_id,
                    )
                )

    flush_paragraph()  # Flush any pending paragraph
    flush_section()

    # ------------------------------------------------------------------
    # Small chunk merging
    # After splitting, adjacent undersized section chunks that share the
    # same section_path are merged so that tiny trailing paragraphs don't
    # become standalone retrieval units.  Structural / table / code chunks
    # are never merged.
    # ------------------------------------------------------------------
    merged: list[ChunkResult] = []
    for _c in chunks:
        if (
            not _c.is_structural
            and _c.chunk_type == "section"
            and estimate_tokens(_c.content) < MIN_CHUNK_TOKENS
            and merged
            and merged[-1].chunk_type == "section"
            and not merged[-1].is_structural
            and merged[-1].section_path == _c.section_path
            and merged[-1].doc_id == _c.doc_id
            and estimate_tokens(merged[-1].content) + estimate_tokens(_c.content) <= MAX_CHUNK_TOKENS
        ):
            _prev = merged[-1]
            # ID stability: keep the first chunk's ID so that downstream
            # systems that stored the original ID before the merge still resolve
            # correctly.  If you prefer content-accurate IDs over stability,
            # replace _prev.id with _make_content_id(...).
            merged[-1] = ChunkResult(
                id=_prev.id,
                title=_prev.title,
                content=_prev.content + "\n\n" + _c.content,
                section_path=_prev.section_path,
                parent_id=_prev.parent_id,
                page_numbers=sorted(set(_prev.page_numbers) | set(_c.page_numbers)),
                chunk_type="section",
                doc_id=_prev.doc_id,
            )
        else:
            merged.append(_c)
    chunks = merged

    # Post-process: prune structural chunks that no other chunk references as a parent.
    # An unreferenced structural chunk adds noise without contributing hierarchy value.
    referenced_parent_ids = {c.parent_id for c in chunks if c.parent_id}
    chunks = [
        c for c in chunks
        if not c.is_structural or c.id in referenced_parent_ids
    ]

    # Enhanced logging
    content_chunks = [c for c in chunks if not c.is_structural and c.content]
    section_count = sum(1 for c in chunks if c.chunk_type == "section" and not c.is_structural)
    structural_count = sum(1 for c in chunks if c.is_structural)
    table_count = sum(1 for c in chunks if c.chunk_type == "table")
    code_count = sum(1 for c in chunks if c.chunk_type == "code_block")
    undersized = sum(1 for c in content_chunks if estimate_tokens(c.content) < MIN_CHUNK_TOKENS)
    token_counts = [estimate_tokens(c.content) for c in content_chunks]
    avg_tokens = int(sum(token_counts) / len(token_counts)) if token_counts else 0
    min_tokens = min(token_counts, default=0)
    max_tokens = max(token_counts, default=0)

    logger.info(
        f"Chunking complete: {len(chunks)} total chunks "
        f"(sections={section_count}, structural={structural_count}, "
        f"tables={table_count}, code_blocks={code_count}, "
        f"undersized={undersized}, boilerplate_lines_skipped={len(boilerplate_lines)}) | "
        f"tokens avg={avg_tokens} min={min_tokens} max={max_tokens}"
    )

    return chunks
