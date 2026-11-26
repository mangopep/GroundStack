# Document parsing

`src/ingestion/pdf_intelligence.py` uses PyMuPDF to open/classify pages and lazily creates a Docling `DocumentConverter`. Native-page classification is based on extracted text length greater than 50 characters. One Docling conversion is attempted for the whole file; each native page is then exported as Markdown. If that export is empty or errors, PyMuPDF text is used and the page status becomes `partial_fallback` when text exists.

Pages classified as scanned are returned with empty text and `skipped` status. Although dependencies include OCR packages, this function does not invoke them. `tables` and `images` fields are returned empty. Table-like content may later be inferred from chunk text, which is not equivalent to preserving a structured table object.

Failure modes include encrypted/corrupt files, resource-heavy PDFs, parser-version changes, and pages with text too short for the simple native/scanned heuristic. Test exact commands, page numbering, mixed layouts, tables, scans, malformed PDFs, and adversarially large inputs.
