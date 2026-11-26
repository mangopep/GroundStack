# First document: current watcher path

The current code can ingest a PDF from a watched directory when the required stores are configured. This is a developer path, not a supported upload workflow.

1. Confirm that Compose services are healthy and that the settings in `.env` match the service credentials.
2. Put a **non-sensitive test PDF** in an isolated test folder. Do not use `data/corpus` if it contains user material.
3. Start the watcher:

   ```bash
   .venv/bin/python -m src.ingestion.watcher --path /absolute/path/to/test-pdfs --max-workers 1
   ```

4. Observe logs and inspect `IngestResult` through the code path. The watcher catches errors in its worker and logs them; it does not provide a durable job status API.
5. Confirm the PDF's object, OpenSearch chunks, and PostgreSQL metadata independently. Cross-store consistency is not guaranteed on failure.

This flow was **not** executed as a live ingestion during the baseline audit. The [walkthrough](../internals/ingestion-engine.md) explains its actual calls and limits. Stop the watcher with Ctrl+C; do not remove files or Docker volumes as a troubleshooting shortcut.
