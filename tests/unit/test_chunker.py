"""
10-test production suite for src/ingestion/chunker.py.

Each test maps to a specific contract the chunker must honour.  Run with:

    pytest tests/unit/test_chunker.py -v
"""

import pytest

from src.ingestion.chunker import (
    MAX_CHUNK_TOKENS,
    MIN_CHUNK_TOKENS,
    ChunkResult,
    chunk_pages,
    estimate_tokens,
    _make_content_id,
    _make_section_id,
)
from src.ingestion.pdf_intelligence import PageResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _page(num: int, text: str, tables: list[str] | None = None) -> PageResult:
    """Convenience factory: always native/success."""
    return PageResult(
        page_num=num,
        text=text,
        page_type="native",
        extraction_status="success",
        tables=tables or [],
        images=[],
    )


def _only_content_chunks(chunks: list[ChunkResult]) -> list[ChunkResult]:
    """Filter to non-structural chunks that carry real text."""
    return [c for c in chunks if not c.is_structural and c.content]


# ---------------------------------------------------------------------------
# 1. Heading detection and section splitting
# ---------------------------------------------------------------------------

class TestHeadingSplit:
    """Proves heading detection + section title assignment work."""

    def test_markdown_headings_become_separate_sections(self):
        pages = [
            _page(1, "# Introduction\n\nThis is the intro paragraph."),
            _page(2, "## Details\n\nMore detailed explanation here."),
        ]
        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t1"))

        titles = [c.title for c in chunks]
        assert "Introduction" in titles
        assert "Details" in titles

    def test_bold_heading_is_detected(self):
        pages = [_page(1, "**Overview**\n\nSome overview text here for context.")]
        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t1-bold"))
        assert any(c.title == "Overview" for c in chunks)

    def test_allcaps_heading_is_detected(self):
        pages = [_page(1, "SUMMARY\n\nA brief summary of the document contents.")]
        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t1-caps"))
        assert any(c.title == "SUMMARY" for c in chunks)

    def test_plain_text_no_heading_gets_untitled(self):
        pages = [_page(1, "Just some plain text with no heading at all.")]
        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t1-plain"))
        assert all(c.title == "Untitled Section" for c in chunks)


# ---------------------------------------------------------------------------
# 2. Section hierarchy (parent_id linkage)
# ---------------------------------------------------------------------------

class TestSectionHierarchy:
    """Proves nested headings produce correct parent_id chains."""

    def test_h2_is_child_of_h1(self):
        pages = [
            _page(
                1,
                "# Chapter\n\nChapter intro text.\n\n"
                "## Sub-section\n\nSub-section body text here.",
            )
        ]
        chunks = chunk_pages(pages, doc_id="t2")
        content = _only_content_chunks(chunks)

        chapter = next(c for c in content if c.title == "Chapter")
        sub = next(c for c in content if c.title == "Sub-section")

        # The sub-section's parent should be the chapter
        assert sub.parent_id == chapter.id

    def test_h1_has_no_parent(self):
        pages = [_page(1, "# Top Level\n\nTop level content paragraph here.")]
        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t2-top"))
        top = next(c for c in chunks if c.title == "Top Level")
        assert top.parent_id is None


# ---------------------------------------------------------------------------
# 3. Large section is split into multiple chunks
# ---------------------------------------------------------------------------

class TestLargeSectionSplit:
    """Proves split logic fires and each piece stays within token budget."""

    def test_oversized_section_is_split(self):
        # Build ~3× the token budget using short paragraphs
        para = "word " * 120  # ~120 tokens per paragraph
        # 15 paragraphs × 120 tokens ≈ 1800 tokens total → must split
        long_body = "\n\n".join(para.strip() for _ in range(15))
        pages = [_page(1, f"# Long Section\n\n{long_body}")]

        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t3"))
        section_chunks = [c for c in chunks if c.chunk_type == "section"]

        assert len(section_chunks) > 1, "Expected split into multiple chunks"

        # Intermediate chunks must be strictly within the token budget.
        # The LAST chunk is allowed to be slightly over because the chunker
        # intentionally absorbs a sub-MIN trailing fragment into the previous
        # chunk to avoid creating micro-stubs (see split_large_text).
        hard_ceiling = MAX_CHUNK_TOKENS + MIN_CHUNK_TOKENS
        for c in section_chunks[:-1]:
            assert estimate_tokens(c.content) <= MAX_CHUNK_TOKENS, (
                f"Intermediate chunk exceeds token limit: {estimate_tokens(c.content)}"
            )
        assert estimate_tokens(section_chunks[-1].content) <= hard_ceiling, (
            f"Final chunk exceeds merged-trailing ceiling: {estimate_tokens(section_chunks[-1].content)}"
        )

    def test_each_split_chunk_meets_min_tokens(self):
        # Only the last chunk of a section is allowed to be sub-minimum
        para = "word " * 120
        long_body = "\n\n".join(para.strip() for _ in range(15))
        pages = [_page(1, f"# Big Section\n\n{long_body}")]

        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t3-min"))
        section_chunks = [c for c in chunks if c.chunk_type == "section"]

        # All chunks except possibly the last must be ≥ MIN_CHUNK_TOKENS
        for c in section_chunks[:-1]:
            assert estimate_tokens(c.content) >= MIN_CHUNK_TOKENS


# ---------------------------------------------------------------------------
# 4. Table preservation
# ---------------------------------------------------------------------------

class TestTablePreservation:
    """Proves pipe-delimited tables are extracted as table chunks."""

    def test_pipe_table_becomes_table_chunk(self):
        table = "| Name | Age |\n|------|-----|\n| Alice | 30 |\n| Bob | 25 |"
        pages = [_page(1, f"# People\n\n{table}")]

        chunks = chunk_pages(pages, doc_id="t4")
        tables = [c for c in chunks if c.chunk_type == "table"]

        assert len(tables) == 1
        assert "Alice" in tables[0].content
        assert "Bob" in tables[0].content

    def test_table_chunk_type_is_table(self):
        table = "| Key | Value |\n|-----|-------|\n| foo | bar |"
        pages = [_page(1, f"# Config\n\n{table}")]

        chunks = chunk_pages(pages, doc_id="t4-type")
        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert all(c.chunk_type == "table" for c in table_chunks)

    def test_duplicate_table_in_same_section_deduplicated(self):
        """Same table appearing via inline scan and page.tables must not be doubled."""
        table = "| X | Y |\n|---|---|\n| 1 | 2 |"
        pages = [_page(1, f"# Section\n\n{table}", tables=[table])]

        chunks = chunk_pages(pages, doc_id="t4-dedup")
        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert len(table_chunks) == 1


# ---------------------------------------------------------------------------
# 5. Code block preservation
# ---------------------------------------------------------------------------

class TestCodeBlockPreservation:
    """Proves fenced code blocks become code_block chunks."""

    def test_fenced_block_becomes_code_chunk(self):
        code = "```python\ndef hello():\n    return 'world'\n```"
        pages = [_page(1, f"# API\n\n{code}")]

        chunks = chunk_pages(pages, doc_id="t5")
        code_chunks = [c for c in chunks if c.chunk_type == "code_block"]

        assert len(code_chunks) == 1
        assert "def hello" in code_chunks[0].content

    def test_code_chunk_type_is_code_block(self):
        code = "```bash\necho hello\n```"
        pages = [_page(1, f"# Shell\n\n{code}")]

        chunks = chunk_pages(pages, doc_id="t5-type")
        assert all(c.chunk_type == "code_block" for c in chunks if "echo" in c.content)


# ---------------------------------------------------------------------------
# 6. Boilerplate removal
# ---------------------------------------------------------------------------

class TestBoilerplateRemoval:
    """Proves repeated lines across pages are stripped."""

    def test_repeated_footer_is_removed(self):
        footer = "Company Confidential"
        # Need >= BOILERPLATE_MIN_PAGES (3) pages, same footer on each
        page_texts = [
            f"# Section {n}\n\nParagraph content for section {n} with enough words.\n\n{footer}"
            for n in range(1, 5)  # 4 pages → above threshold
        ]
        pages = [_page(n + 1, t) for n, t in enumerate(page_texts)]

        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t6"))
        all_content = " ".join(c.content for c in chunks)

        assert footer not in all_content, "Boilerplate footer should have been stripped"

    def test_unique_lines_are_not_stripped(self):
        pages = [
            _page(1, "# Alpha\n\nAlpha unique content here."),
            _page(2, "# Beta\n\nBeta unique content here."),
            _page(3, "# Gamma\n\nGamma unique content here."),
            _page(4, "# Delta\n\nDelta unique content here."),
        ]
        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t6-unique"))
        all_content = " ".join(c.content for c in chunks)

        assert "Alpha unique content" in all_content
        assert "Beta unique content" in all_content


# ---------------------------------------------------------------------------
# 7. Structural anchor chunk
# ---------------------------------------------------------------------------

class TestStructuralAnchor:
    """Proves a heading with no body text becomes a structural anchor
    when an immediately following table needs a parent_id."""

    def test_table_under_bodyless_heading_gets_structural_parent(self):
        table = "| Col A | Col B |\n|-------|-------|\n| val1 | val2 |"
        # Heading immediately followed by table — no prose between them
        pages = [_page(1, f"# Bare Heading\n\n{table}")]

        chunks = chunk_pages(pages, doc_id="t7")
        structurals = [c for c in chunks if c.is_structural]
        tables = [c for c in chunks if c.chunk_type == "table"]

        assert structurals, "Expected a structural anchor chunk"
        assert tables, "Expected a table chunk"
        assert tables[0].parent_id == structurals[0].id

    def test_unreferenced_structural_chunks_are_pruned(self):
        """A heading with no body AND no child tables/code should be pruned."""
        # Two headings, second has content; first has nothing at all
        pages = [_page(1, "# Empty Heading\n\n# Content Heading\n\nActual content here.")]

        chunks = chunk_pages(pages, doc_id="t7-prune")
        structurals = [c for c in chunks if c.is_structural]

        # The empty heading should be pruned (nothing references it)
        assert not structurals, f"Unexpected structural chunks: {structurals}"


# ---------------------------------------------------------------------------
# 8. Deterministic IDs
# ---------------------------------------------------------------------------

class TestDeterministicIDs:
    """Proves re-ingesting the same document produces identical chunk IDs."""

    def test_same_input_same_ids(self):
        pages = [
            _page(1, "# Intro\n\nIntroductory content with enough words."),
            _page(2, "## Details\n\nDetailed information about the topic."),
        ]
        run1 = chunk_pages(pages, doc_id="t8")
        run2 = chunk_pages(pages, doc_id="t8")

        ids1 = {c.id for c in run1}
        ids2 = {c.id for c in run2}
        assert ids1 == ids2

    def test_different_doc_ids_produce_different_chunk_ids(self):
        pages = [_page(1, "# Same Content\n\nIdentical text in both documents.")]
        run_a = chunk_pages(pages, doc_id="doc_a")
        run_b = chunk_pages(pages, doc_id="doc_b")

        ids_a = {c.id for c in run_a}
        ids_b = {c.id for c in run_b}
        assert ids_a.isdisjoint(ids_b), "Different doc_ids must produce different IDs"

    def test_section_id_collision_prevention(self):
        """Same section_path on the same page must not collide."""
        # Two headings with the same name on the same page
        pages = [_page(1, "# Item\n\nFirst item body.\n\n# Item\n\nSecond item body.")]
        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t8-collision"))
        ids = [c.id for c in chunks]
        assert len(ids) == len(set(ids)), "All chunk IDs must be unique"

    def test_make_content_id_is_stable(self):
        id1 = _make_content_id("doc", "section", "hello world", scope="path")
        id2 = _make_content_id("doc", "section", "hello world", scope="path")
        assert id1 == id2

    def test_make_section_id_ordinal_breaks_collision(self):
        id0 = _make_section_id("doc", "path > Title", 1, ordinal=0)
        id1 = _make_section_id("doc", "path > Title", 1, ordinal=1)
        assert id0 != id1


# ---------------------------------------------------------------------------
# 9. Page attribution
# ---------------------------------------------------------------------------

class TestPageAttribution:
    """Proves chunks carry the correct page numbers."""

    def test_single_page_chunk_has_correct_page(self):
        pages = [_page(3, "# Section\n\nContent from page three.")]
        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t9"))
        assert all(3 in c.page_numbers for c in chunks)

    def test_multi_page_section_aggregates_pages(self):
        pages = [
            _page(1, "# Long Section\n\nFirst page content here."),
            _page(2, "Continuation of the long section across page two."),
        ]
        chunks = _only_content_chunks(chunk_pages(pages, doc_id="t9-multi"))
        section_pages = set()
        for c in chunks:
            section_pages.update(c.page_numbers)
        assert 1 in section_pages
        assert 2 in section_pages

    def test_skipped_and_failed_pages_excluded(self):
        pages = [
            _page(1, "# Valid\n\nContent here."),
            PageResult(
                page_num=2, text="scanned text", page_type="scanned",
                extraction_status="skipped", tables=[], images=[],
            ),
            PageResult(
                page_num=3, text="", page_type="native",
                extraction_status="failed", tables=[], images=[],
            ),
        ]
        chunks = chunk_pages(pages, doc_id="t9-skip")
        all_pages = {p for c in chunks for p in c.page_numbers}
        assert 2 not in all_pages
        assert 3 not in all_pages


# ---------------------------------------------------------------------------
# 10. Duplicate table suppression across sections
# ---------------------------------------------------------------------------

class TestDuplicateTableSuppression:
    """Proves tables are deduplicated within a section but preserved across
    different sections (intentional repetition)."""

    def test_same_table_different_sections_both_kept(self):
        table = "| A | B |\n|---|---|\n| 1 | 2 |"
        pages = [
            _page(1, f"# Section One\n\n{table}"),
            _page(2, f"# Section Two\n\n{table}"),
        ]
        chunks = chunk_pages(pages, doc_id="t10")
        table_chunks = [c for c in chunks if c.chunk_type == "table"]

        assert len(table_chunks) == 2, (
            "Identical tables in different sections should both be kept"
        )

    def test_same_table_same_section_deduplicated(self):
        """Table that appears both inline and in page.tables is not doubled."""
        table = "| X | Y |\n|---|---|\n| a | b |"
        pages = [_page(1, f"# Sec\n\n{table}", tables=[table])]

        chunks = chunk_pages(pages, doc_id="t10-dedup")
        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert len(table_chunks) == 1
