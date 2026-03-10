"""
Background ingestion worker for RAG platform.

This module implements the IngestWorker class that:
- registers itself as the INGEST_PDF handler on a TaskQueue
- runs the ingest_pdf pipeline with retry logic
- moves failed files to data/failed/
- creates symlinks for successful files in data/processed/
- updates document_metadata status through the ingestion lifecycle
- notifies freshness invalidator when a document is re-ingested
- supports running as a standalone process: python -m src.workers.ingest_worker

Integration pattern
-------------------
IngestWorker does NOT pull tasks directly from the queue.  Instead it
registers ``handle_ingest_task`` as the handler for ``TaskType.INGEST_PDF``
via ``queue.register_handler()``.  The TaskQueue's own worker loop handles
all dequeueing, priority scheduling, concurrency, and task-lifecycle
transitions (QUEUED → PROCESSING → COMPLETED / FAILED).
"""

import asyncio
import logging
import os
import shutil
import traceback
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

import psycopg

from src.config.settings import get_settings
from src.workers.queue import QueuedTask, TaskQueue, TaskType, get_queue

logger = logging.getLogger(__name__)

# =============================================================================
# FRESHNESS NOTIFIER (PLACEHOLDER)
# =============================================================================


def _notify_freshness_invalidator(doc_id: str) -> None:
    """
    Notify the freshness invalidator that a document has been re-ingested.

    This is a placeholder implementation that logs the event.
    If a real freshness invalidator exists in the project, import and call it here.

    Args:
        doc_id: The document ID that was re-ingested
    """
    # Try to import and call the real freshness invalidator.
    # Freshness invalidation is best-effort: any failure must not
    # propagate and break the ingestion success path.
    try:
        from src.ingestion.freshness import invalidate_freshness

        invalidate_freshness(doc_id)
        logger.info("Freshness invalidated for doc_id=%s", doc_id)
    except ImportError:
        logger.debug("Freshness invalidation triggered for doc_id=%s (no-op)", doc_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("Freshness invalidation failed for doc_id=%s: %s", doc_id, e)


# =============================================================================
# INGEST WORKER
# =============================================================================


class IngestWorker:
    """
    Background ingestion worker for processing PDF ingestion tasks.

    IngestWorker owns the *business logic* for ingestion: retry scheduling,
    failed-file management, processed-symlink creation, metadata status
    updates, and freshness invalidation.

    It integrates with TaskQueue by **registering** ``handle_ingest_task``
    as the handler for ``TaskType.INGEST_PDF``.  The queue retains full
    ownership of dequeueing, priority ordering, worker concurrency, and
    task-lifecycle transitions (QUEUED → PROCESSING → COMPLETED / FAILED).
    IngestWorker never reads from or writes to any queue-internal attribute.
    """

    def __init__(
        self,
        queue: TaskQueue | None = None,
        max_attempts: int = 3,
        failed_dir: str | Path = "data/failed",
        processed_dir: str | Path = "data/processed",
    ):
        """
        Initialize the IngestWorker.

        Args:
            queue: TaskQueue instance (will use get_queue() if not provided)
            max_attempts: Maximum number of retry attempts (default: 3)
            failed_dir: Directory for failed files (default: data/failed)
            processed_dir: Directory for symlinks to processed files (default: data/processed)
        """
        self._queue = queue
        self._max_attempts = max_attempts
        self._failed_dir = Path(failed_dir)
        self._processed_dir = Path(processed_dir)

        self._ensure_dirs()

        logger.info(
            "IngestWorker initialized: max_attempts=%d, failed_dir=%s, processed_dir=%s",
            max_attempts,
            self._failed_dir,
            self._processed_dir,
        )

    def _ensure_dirs(self) -> None:
        """Ensure failed and processed directories exist."""
        self._failed_dir.mkdir(parents=True, exist_ok=True)
        self._processed_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Ensured directories exist: %s, %s", self._failed_dir, self._processed_dir)

    @property
    def queue(self) -> TaskQueue:
        """Get the task queue (lazy initialization)."""
        if self._queue is None:
            self._queue = get_queue()
        return self._queue

    # =========================================================================
    # WORKER LIFECYCLE
    # =========================================================================

    def register(self) -> None:
        """
        Register ``handle_ingest_task`` as the INGEST_PDF handler on the queue.

        Must be called before ``run_forever()`` (or before the queue starts
        processing tasks).  Replaces any previously registered handler for
        ``TaskType.INGEST_PDF``.
        """
        self.queue.register_handler(TaskType.INGEST_PDF, self.handle_ingest_task)
        logger.info("IngestWorker registered as INGEST_PDF handler")

    async def run_forever(self) -> None:
        """
        Register the handler and run the queue until it is stopped.

        Blocks until the underlying TaskQueue finishes (i.e. until
        ``stop()`` is called from another coroutine or the task is
        cancelled).
        """
        self.register()
        logger.info("IngestWorker starting queue")
        try:
            await self.queue.process()
        except asyncio.CancelledError:
            logger.info("IngestWorker cancelled")

    async def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the worker gracefully by stopping the underlying queue.

        Args:
            timeout: Maximum seconds to wait for in-flight tasks before
                     force-cancelling queue workers.
        """
        logger.info("Stopping IngestWorker gracefully...")
        await self.queue.stop(timeout=timeout)
        logger.info("IngestWorker stopped")

    # =========================================================================
    # INGEST_PDF HANDLER  (called by TaskQueue for every INGEST_PDF task)
    # =========================================================================

    async def handle_ingest_task(self, task: QueuedTask) -> None:
        """
        Handle a single INGEST_PDF task dispatched by the TaskQueue.

        This is the public handler registered via ``register()``.  The queue
        calls it inside its own worker loop after transitioning the task to
        PROCESSING.  If this method raises, the queue marks the task FAILED.

        Args:
            task: The QueuedTask with ``task_type == TaskType.INGEST_PDF``
        """
        task_id = task.task_id
        payload = task.payload
        pdf_path_str = payload.get("pdf_path")

        logger.info(
            "Handling ingest task: task_id=%s, pdf_path=%s",
            task_id,
            pdf_path_str,
        )

        if not pdf_path_str:
            raise ValueError(f"Missing pdf_path in task payload: task_id={task_id}")

        pdf_path = Path(pdf_path_str)
        doc_id: str | None = payload.get("doc_id")
        reingest: bool = payload.get("reingest", False)

        # Detect reingestion *before* we start (doc_id may be known from payload)
        is_reingestion = reingest or (doc_id is not None and self._document_exists(doc_id))

        # Run ingestion with retries
        try:
            result = await self._run_ingest_with_retries(pdf_path, payload)
        except Exception as e:
            logger.exception(
                "Ingestion failed after all retries: task_id=%s, pdf_path=%s, error=%s",
                task_id,
                pdf_path_str,
                e,
            )
            # Update metadata if we know the doc_id
            await self._update_document_status(doc_id, "failed", str(e))
            # Move file to failed directory and write error log
            await self._move_to_failed(pdf_path, e)
            # Re-raise so the queue transitions the task to FAILED
            raise

        # ── Success path ──────────────────────────────────────────────────
        await self._update_document_status(result.doc_id, "done", None)
        await self._create_processed_symlink(pdf_path, result.doc_id)

        if is_reingestion:
            _notify_freshness_invalidator(result.doc_id)
            logger.info(
                "Re-ingestion completed, notified invalidator: doc_id=%s",
                result.doc_id,
            )

        logger.info(
            "Ingestion succeeded: task_id=%s, doc_id=%s, pages=%d, chunks=%d",
            task_id,
            result.doc_id,
            result.page_count,
            result.chunk_count,
        )

    async def _run_ingest_with_retries(
        self, pdf_path: Path, task_payload: dict[str, Any]
    ) -> Any:
        """
        Run the ingestion with retry logic.

        Args:
            pdf_path: Path to the PDF file
            task_payload: Original task payload

        Returns:
            IngestResult from successful ingestion

        Raises:
            Exception: If all retry attempts fail
        """
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                logger.info(
                    "Ingestion attempt %d/%d: pdf_path=%s",
                    attempt,
                    self._max_attempts,
                    pdf_path,
                )

                # Run the synchronous ingestion in a thread pool.
                # Import here to avoid a hard dependency at module load time.
                from src.ingestion.index_builder import ingest_pdf  # noqa: PLC0415
                result = await asyncio.to_thread(ingest_pdf, str(pdf_path))

                logger.info(
                    "Ingestion attempt %d succeeded: pdf_path=%s, doc_id=%s",
                    attempt,
                    pdf_path,
                    result.doc_id,
                )

                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    "Ingestion attempt %d/%d failed: pdf_path=%s, error=%s",
                    attempt,
                    self._max_attempts,
                    pdf_path,
                    e,
                )

                # Don't wait after the last attempt
                if attempt < self._max_attempts:
                    # Exponential backoff: 1s, 2s, 4s, etc.
                    wait_time = 2 ** (attempt - 1)
                    await asyncio.sleep(wait_time)

        # All attempts failed
        raise last_error or Exception("Unknown ingestion error")

    # =========================================================================
    # FILESYSTEM HELPERS
    # =========================================================================

    async def _create_processed_symlink(self, pdf_path: Path, doc_id: str) -> None:
        """
        Create a symlink in the processed directory pointing to the original file.

        Args:
            pdf_path: Path to the original PDF file
            doc_id: Document ID for the symlink name
        """
        try:
            # Use doc_id as the symlink name
            symlink_name = f"{doc_id}.pdf"
            symlink_path = self._processed_dir / symlink_name

            # Remove existing symlink if it exists
            if symlink_path.exists() or symlink_path.is_symlink():
                symlink_path.unlink()

            # Create symlink
            os.symlink(pdf_path.resolve(), symlink_path)
            logger.info("Created processed symlink: %s -> %s", symlink_path, pdf_path)

        except Exception as e:
            # Log warning but don't fail the ingestion
            logger.warning(
                "Failed to create processed symlink for %s: %s",
                pdf_path,
                e,
            )

    async def _move_to_failed(self, pdf_path: Path, error: Exception) -> None:
        """
        Move a failed file to the failed directory and write an error log.

        Args:
            pdf_path: Path to the failed PDF file
            error: The exception that caused the failure
        """
        try:
            # Generate safe filename with timestamp if needed
            base_name = pdf_path.name
            failed_path = self._failed_dir / base_name

            # Avoid overwriting: add timestamp suffix if file exists
            if failed_path.exists():
                timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
                name_without_ext = base_name.replace(".pdf", "")
                failed_path = self._failed_dir / f"{name_without_ext}_{timestamp}.pdf"

            # Move the file
            shutil.move(str(pdf_path), str(failed_path))
            logger.info("Moved failed file to: %s", failed_path)

            # Write error log
            await self._write_error_log(failed_path, pdf_path, error)

        except Exception as e:
            logger.error(
                "Failed to move file to failed directory: pdf_path=%s, error=%s",
                pdf_path,
                e,
            )

    async def _write_error_log(
        self, failed_path: Path, original_path: Path, error: Exception
    ) -> None:
        """
        Write an error log file alongside the failed file.

        Args:
            failed_path: Path to the failed file
            original_path: Original path of the file
            error: The exception that caused the failure
        """
        try:
            error_log_path = failed_path.with_suffix(failed_path.suffix + ".error.log")

            timestamp = datetime.now(UTC).isoformat()
            traceback_str = traceback.format_exception(type(error), error, error.__traceback__)

            content = f"""Error Log
========
Timestamp: {timestamp}
Original File: {original_path}
Failed File: {failed_path}

Exception: {type(error).__name__}: {error}

Traceback:
{''.join(traceback_str)}
"""

            error_log_path.write_text(content)
            logger.info("Wrote error log: %s", error_log_path)

        except Exception as e:
            logger.error("Failed to write error log: %s", e)

    # =========================================================================
    # DATABASE HELPERS
    # =========================================================================

    def _document_exists(self, doc_id: str) -> bool:
        """
        Check if a document already exists in the metadata table.

        Args:
            doc_id: The document ID to check

        Returns:
            True if document exists, False otherwise
        """
        if not doc_id:
            return False

        try:
            settings = get_settings()
            cfg = settings.database

            conninfo = (
                f"host={cfg.host} port={cfg.port} user={cfg.user} "
                f"password={cfg.password} dbname={cfg.db}"
            )

            with psycopg.connect(conninfo) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT 1 FROM document_metadata WHERE doc_id = %s",
                        (doc_id,),
                    )
                    return cur.fetchone() is not None

        except Exception as e:
            logger.debug("Error checking document existence: %s", e)
            return False

    async def _update_document_status(
        self, doc_id: str | None, status: str, error: str | None
    ) -> None:
        """
        Update the document metadata status.

        Note: This helper assumes a 'status' column exists in the document_metadata
        table. If it doesn't exist yet, this will fail gracefully.

        Args:
            doc_id: The document ID (can be None for new documents)
            status: The new status (pending, processing, done, failed)
            error: Optional error message for failed status
        """
        if not doc_id:
            logger.debug("No doc_id provided, skipping status update")
            return

        try:
            settings = get_settings()
            cfg = settings.database

            conninfo = (
                f"host={cfg.host} port={cfg.port} user={cfg.user} "
                f"password={cfg.password} dbname={cfg.db}"
            )

            with psycopg.connect(conninfo) as conn:
                with conn.cursor() as cur:
                    # Try to update with status column (may fail if column doesn't exist)
                    try:
                        cur.execute(
                            """
                            UPDATE document_metadata 
                            SET status = %s, error = %s, updated_at = %s
                            WHERE doc_id = %s
                            """,
                            (status, error, datetime.now(UTC), doc_id),
                        )

                        if cur.rowcount == 0:
                            # Document doesn't exist, insert it
                            cur.execute(
                                """
                                INSERT INTO document_metadata (doc_id, status, error, ingested_at)
                                VALUES (%s, %s, %s, %s)
                                """,
                                (doc_id, status, error, datetime.now(UTC)),
                            )

                        conn.commit()
                        logger.debug(
                            "Updated document status: doc_id=%s, status=%s",
                            doc_id,
                            status,
                        )

                    except psycopg.errors.UndefinedColumn:
                        # Status column doesn't exist, log and continue
                        logger.debug(
                            "Status column not found in document_metadata, skipping update"
                        )
                        conn.rollback()

        except Exception as e:
            # Log error but don't fail the ingestion
            logger.error(
                "Failed to update document status: doc_id=%s, status=%s, error=%s",
                doc_id,
                status,
                e,
            )


# =============================================================================
# STANDALONE ENTRYPOINT
# =============================================================================


def main() -> None:
    """
    Main entrypoint for running the worker as a standalone process.

    Usage:
        python -m src.workers.ingest_worker

    Optional arguments:
        --max-attempts: Maximum retry attempts (default: 3)
        --failed-dir: Directory for failed files (default: data/failed)
        --processed-dir: Directory for processed symlinks (default: data/processed)
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the PDF ingestion worker"
    )
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=3,
        help="Maximum retry attempts (default: 3)",
    )
    parser.add_argument(
        "--failed-dir",
        type=str,
        default="data/failed",
        help="Directory for failed files (default: data/failed)",
    )
    parser.add_argument(
        "--processed-dir",
        type=str,
        default="data/processed",
        help="Directory for processed symlinks (default: data/processed)",
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting IngestWorker...")

    # Create and start the worker
    worker = IngestWorker(
        max_attempts=args.max_attempts,
        failed_dir=args.failed_dir,
        processed_dir=args.processed_dir,
    )

    async def _run() -> None:
        """
        Coroutine executed by asyncio.run().

        asyncio.run() cancels this task on KeyboardInterrupt and then
        awaits it, so the finally block is guaranteed to execute, giving
        in-flight tasks a chance to finish before the process exits.
        """
        try:
            await worker.run_forever()
        except asyncio.CancelledError:
            logger.info("Received interrupt signal, stopping worker...")
        finally:
            await worker.stop()
            logger.info("IngestWorker shutdown complete")

    asyncio.run(_run())


if __name__ == "__main__":
    main()

