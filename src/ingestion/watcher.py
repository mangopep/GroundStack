"""
Filesystem watcher for automatic PDF ingestion in a RAG platform.

This module monitors a directory for new or modified PDF files,
classifies them by priority, and queues them for ingestion.
"""

import argparse
import concurrent.futures
import heapq
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from watchdog.events import FileSystemEventHandler, FileSystemEvent
from watchdog.observers import Observer

from src.ingestion.index_builder import ingest_pdf

logger = logging.getLogger(__name__)

# =============================================================================
# PRIORITY CLASSIFICATION
# =============================================================================


def classify_priority(file_path: Path) -> tuple[str, int]:
    """
    Classify a PDF file into a priority bucket based on its filename.

    Priority rules (case-insensitive):
    - P0: filenames containing 'defect' or 'rca'
    - P1: filenames containing 'cli' or 'config'
    - P2: filenames containing 'handbook'
    - P3: everything else

    Args:
        file_path: Path to the PDF file

    Returns:
        Tuple of (priority_label, priority_number)
        where lower number means higher priority
    """
    filename_lower = file_path.name.lower()

    # P0: defect or RCA
    if "defect" in filename_lower or "rca" in filename_lower:
        return ("P0", 0)

    # P1: cli or config
    if "cli" in filename_lower or "config" in filename_lower:
        return ("P1", 1)

    # P2: handbook
    if "handbook" in filename_lower:
        return ("P2", 2)

    # P3: everything else
    return ("P3", 3)


# =============================================================================
# JOB DATA STRUCTURE
# =============================================================================


@dataclass(order=True)
class IngestionJob:
    """
    Represents a PDF ingestion job in the priority queue.

    Ordering is by priority_num first, then by counter (FIFO for same priority).
    """
    priority_num: int
    counter: int
    file_path: Path = field(compare=False)
    priority_label: str = field(compare=False)
    enqueue_time: float = field(compare=False)


# =============================================================================
# INGESTION WATCHER
# =============================================================================


class IngestionWatcher:
    """
    Filesystem watcher for automatic PDF ingestion.

    Monitors a directory for new or modified PDF files, classifies them
    by priority, and processes them using the index_builder.
    """

    def __init__(
        self,
        watch_path: str | Path,
        max_workers: int = 4,
        debounce_seconds: float = 2.0,
    ):
        """
        Initialize the ingestion watcher.

        Args:
            watch_path: Directory to watch for PDF files
            max_workers: Maximum number of parallel ingestion workers
            debounce_seconds: Time window to debounce duplicate events

        Raises:
            FileNotFoundError: If watch_path does not exist
            NotADirectoryError: If watch_path is not a directory
        """
        self.watch_path = Path(watch_path).resolve()

        # Validate path
        if not self.watch_path.exists():
            raise FileNotFoundError(f"Watch path does not exist: {self.watch_path}")
        if not self.watch_path.is_dir():
            raise NotADirectoryError(f"Watch path is not a directory: {self.watch_path}")

        self.max_workers = max_workers
        self.debounce_seconds = debounce_seconds

        # Priority queue (min-heap)
        self._pending_jobs: list[IngestionJob] = []
        self._job_counter = 0
        self._queue_lock = threading.Lock()

        # Thread pool for ingestion workers
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="ingestion_worker"
        )
        self._active_futures: set[concurrent.futures.Future] = set()
        self._futures_lock = threading.Lock()

        # Dispatch thread
        self._dispatch_thread: threading.Thread | None = None
        self._dispatch_running = threading.Event()

        # Debounce tracking
        self._last_seen: dict[Path, float] = {}
        self._debounce_lock = threading.Lock()

        # Watchdog
        self._observer: Observer | None = None
        self._event_handler: PDFEventHandler | None = None

        # Running state
        self._running = threading.Event()

        logger.info(
            "IngestionWatcher initialized: path=%s, max_workers=%d, debounce=%.1fs",
            self.watch_path,
            self.max_workers,
            self.debounce_seconds,
        )

    def start(self) -> None:
        """Start watching the directory and processing jobs."""
        if self._running.is_set():
            logger.warning("Watcher already running")
            return

        # Setup watchdog
        self._event_handler = PDFEventHandler(self)
        self._observer = Observer()
        self._observer.schedule(
            self._event_handler,
            str(self.watch_path),
            recursive=False,  # Non-recursive by default
        )
        self._observer.start()

        # Start dispatch thread
        self._dispatch_running.set()
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop,
            name="dispatch_loop",
            daemon=True,
        )
        self._dispatch_thread.start()

        self._running.set()

        logger.info(
            "Watcher started: watching %s (non-recursive)",
            self.watch_path
        )

    def stop(self) -> None:
        """Stop watching and shut down cleanly."""
        if not self._running.is_set():
            logger.warning("Watcher not running")
            return

        logger.info("Stopping watcher...")

        # Stop watchdog
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None

        # Stop dispatch thread
        self._dispatch_running.clear()
        if self._dispatch_thread is not None:
            self._dispatch_thread.join(timeout=5)
            self._dispatch_thread = None

        # Wait for active futures
        with self._futures_lock:
            if self._active_futures:
                logger.info(
                    "Waiting for %d active jobs to complete...",
                    len(self._active_futures)
                )
                concurrent.futures.wait(
                    self._active_futures,
                    timeout=30,
                )

        # Shutdown executor
        self._executor.shutdown(wait=True, cancel_futures=False)

        self._running.clear()
        logger.info("Watcher stopped")

    def enqueue_file(self, file_path: Path) -> None:
        """
        Enqueue a PDF file for ingestion.

        Args:
            file_path: Path to the PDF file
        """
        # Validate it's a PDF
        if file_path.suffix.lower() != ".pdf":
            logger.debug("Ignoring non-PDF file: %s", file_path.name)
            return

        # Check for temporary/incomplete files
        temp_patterns = (".part", ".tmp", "~")
        if file_path.name.endswith(temp_patterns):
            logger.debug("Ignoring temporary file: %s", file_path.name)
            return

        # File-stability check: ensure the file is not still being written
        if not self._is_file_stable(file_path):
            logger.debug("File still being written, skipping: %s", file_path.name)
            return

        # Debounce: check last seen timestamp
        current_time = time.monotonic()
        with self._debounce_lock:
            last_seen = self._last_seen.get(file_path)
            if last_seen is not None:
                time_since_last = current_time - last_seen
                if time_since_last < self.debounce_seconds:
                    logger.debug(
                        "Debouncing file (%.1fs since last event): %s",
                        time_since_last,
                        file_path.name,
                    )
                    return
            # Update last seen timestamp
            self._last_seen[file_path] = current_time

        # Classify priority
        priority_label, priority_num = classify_priority(file_path)
        logger.info(
            "Enqueueing file: %s (priority=%s)",
            file_path.name,
            priority_label,
        )

        # Create job
        with self._queue_lock:
            self._job_counter += 1
            job = IngestionJob(
                priority_num=priority_num,
                counter=self._job_counter,
                file_path=file_path,
                priority_label=priority_label,
                enqueue_time=current_time,
            )
            heapq.heappush(self._pending_jobs, job)

        logger.debug(
            "Queue depth after enqueue: %d",
            self._get_queue_depth(),
        )

    def _is_file_stable(self, file_path: Path, poll_interval: float = 0.5) -> bool:
        """
        Return True only if the file exists and its size has not changed
        after waiting poll_interval seconds.

        Args:
            file_path: Path to check
            poll_interval: Seconds to wait between size samples
        """
        try:
            size_before = file_path.stat().st_size
            time.sleep(poll_interval)
            size_after = file_path.stat().st_size
            return size_before == size_after
        except OSError:
            return False

    def _get_queue_depth(self) -> int:
        """Get the current queue depth."""
        with self._queue_lock:
            return len(self._pending_jobs)

    def _dispatch_loop(self) -> None:
        """
        Background thread that dispatches jobs to workers.

        Continuously checks for pending jobs and submits them while
        worker slots are available. Higher priority jobs are chosen first.
        """
        logger.debug("Dispatch loop started")

        while self._dispatch_running.is_set():
            # Check if we can dispatch more jobs
            active_count = self._get_active_count()

            if active_count >= self.max_workers:
                # All workers busy, wait a bit
                time.sleep(0.1)
                continue

            # Get next job from queue
            with self._queue_lock:
                if not self._pending_jobs:
                    time.sleep(0.1)
                    continue

                # Pop highest priority job (lowest priority_num first)
                job = heapq.heappop(self._pending_jobs)

            # Submit job to executor
            self._submit_job(
                job.file_path,
                job.priority_label,
            )

        logger.debug("Dispatch loop stopped")

    def _get_active_count(self) -> int:
        """Get the number of active (running) futures."""
        with self._futures_lock:
            # Filter out completed futures
            completed = set()
            for f in self._active_futures:
                if f.done():
                    completed.add(f)
            self._active_futures -= completed
            return len(self._active_futures)

    def _submit_job(
        self,
        file_path: Path,
        priority_label: str,
    ) -> None:
        """
        Submit an ingestion job to the thread pool.

        Args:
            file_path: Path to the PDF file
            priority_label: Priority label (P0, P1, P2, P3)
        """
        logger.info(
            "Submitting job: %s (priority=%s)",
            file_path.name,
            priority_label,
        )

        future = self._executor.submit(
            self._run_ingestion,
            file_path,
            priority_label,
        )

        with self._futures_lock:
            self._active_futures.add(future)

        # Add callback to handle completion
        future.add_done_callback(
            lambda f: self._on_job_done(f, file_path, priority_label)
        )

    def _run_ingestion(self, file_path: Path, priority_label: str) -> None:
        """
        Run the ingestion for a PDF file.

        Args:
            file_path: Path to the PDF file
            priority_label: Priority label for logging
        """
        logger.info("Starting ingestion: %s (priority=%s)", file_path.name, priority_label)

        try:
            result = ingest_pdf(file_path)
            logger.info(
                "Ingestion complete: %s - pages=%d, chunks=%d, status=%s",
                file_path.name,
                result.page_count,
                result.chunk_count,
                result.status,
            )
        except Exception as e:
            logger.exception("Ingestion failed for %s: %s", file_path.name, e)

    def _on_job_done(
        self,
        future: concurrent.futures.Future,
        file_path: Path,
        priority_label: str,
    ) -> None:
        """
        Callback when a job completes.

        Args:
            future: The completed future
            file_path: Path to the PDF file
            priority_label: Priority label for logging
        """
        with self._futures_lock:
            self._active_futures.discard(future)

        if future.exception() is not None:
            logger.error(
                "Job failed: %s (priority=%s)",
                file_path.name,
                priority_label,
                exc_info=future.exception(),
            )
        else:
            logger.debug(
                "Job completed: %s (priority=%s)",
                file_path.name,
                priority_label,
            )


# =============================================================================
# WATCHDOG EVENT HANDLER
# =============================================================================


class PDFEventHandler(FileSystemEventHandler):
    """
    Watchdog event handler for PDF files.

    Handles created and modified events for PDF files.
    """

    def __init__(self, watcher: IngestionWatcher):
        """
        Initialize the event handler.

        Args:
            watcher: The IngestionWatcher instance to notify
        """
        super().__init__()
        self.watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        logger.debug("File created: %s", file_path.name)
        self.watcher.enqueue_file(file_path)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        logger.debug("File modified: %s", file_path.name)
        self.watcher.enqueue_file(file_path)


# =============================================================================
# CLI ENTRYPOINT
# =============================================================================


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Watch a directory for PDF files and ingest them automatically."
    )
    parser.add_argument(
        "--path",
        type=str,
        required=True,
        help="Directory to watch for PDF files",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Maximum number of parallel workers (default: 4)",
    )
    parser.add_argument(
        "--debounce-seconds",
        type=float,
        default=2.0,
        help="Debounce window in seconds (default: 2.0)",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger.info("Starting ingestion watcher...")
    logger.info("Watching directory: %s", args.path)
    logger.info("Max workers: %d", args.max_workers)
    logger.info("Debounce seconds: %.1f", args.debounce_seconds)

    watcher: IngestionWatcher | None = None
    try:
        watcher = IngestionWatcher(
            watch_path=args.path,
            max_workers=args.max_workers,
            debounce_seconds=args.debounce_seconds,
        )
        watcher.start()

        # Keep running until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        if watcher:
            watcher.stop()
        logger.info("Shutdown complete")
    except FileNotFoundError as e:
        logger.error("Error: %s", e)
        raise SystemExit(1)
    except NotADirectoryError as e:
        logger.error("Error: %s", e)
        raise SystemExit(1)


if __name__ == "__main__":
    main()

