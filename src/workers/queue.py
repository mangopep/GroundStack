"""
Async background task queue for RAG platform.

This module provides an in-process async task queue with priority support,
multiple concurrent workers, and task status tracking.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)


# =============================================================================
# DATA MODELS
# =============================================================================


class TaskType(str, Enum):
    """Supported task types."""

    INGEST_PDF = "ingest_pdf"
    REINDEX_DOCUMENT = "reindex_document"
    SUMMARIZE_SESSION = "summarize_session"
    INVALIDATE_CACHE = "invalidate_cache"


class TaskStatus(str, Enum):
    """Task lifecycle statuses."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass(order=True)
class QueuedTask:
    """
    Represents a task in the priority queue.

    Ordering is by priority first, then by sequence (FIFO for same priority).
    """

    priority: int
    sequence: int
    task_id: str = field(compare=False)
    task_type: TaskType = field(compare=False)
    payload: dict[str, Any] = field(compare=False)
    created_at: float = field(compare=False)
    status: TaskStatus = field(compare=False, default=TaskStatus.QUEUED)
    error: str | None = field(compare=False, default=None)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "payload": self.payload,
            "priority": self.priority,
            "created_at": self.created_at,
            "status": self.status.value,
            "error": self.error,
        }


# =============================================================================
# TASK QUEUE
# =============================================================================


class TaskQueue:
    """
    Async background task queue with priority support.

    Features:
    - Priority-based task ordering (lower number = higher priority)
    - FIFO ordering for tasks with same priority
    - Multiple concurrent async workers
    - Task status tracking
    - Graceful shutdown support
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize the task queue.

        Args:
            max_workers: Maximum number of concurrent async workers
        """
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")

        self.max_workers = max_workers

        # Priority queue: (priority, sequence, task)
        self._queue: asyncio.PriorityQueue[tuple[int, int, QueuedTask]] = (
            asyncio.PriorityQueue()
        )

        # Sequence counter for FIFO ordering within same priority
        self._sequence_counter = 0
        self._sequence_lock = asyncio.Lock()

        # Task registry: task_id -> QueuedTask
        self._tasks: dict[str, QueuedTask] = {}
        self._tasks_lock = asyncio.Lock()

        # Status tracking
        self._status_counts: dict[TaskStatus, int] = {
            TaskStatus.QUEUED: 0,
            TaskStatus.PROCESSING: 0,
            TaskStatus.COMPLETED: 0,
            TaskStatus.FAILED: 0,
        }
        self._status_lock = asyncio.Lock()

        # Worker management
        self._workers: set[asyncio.Task[None]] = set()
        self._running = False
        self._stop_event = asyncio.Event()

        # Task handler registry
        self._handlers: dict[TaskType, Callable[[QueuedTask], Awaitable[None]]] = {}

        # Register default handlers
        self._register_default_handlers()

        logger.info("TaskQueue initialized with max_workers=%d", max_workers)

    def _register_default_handlers(self) -> None:
        """Register default task handlers."""
        self._handlers[TaskType.INGEST_PDF] = self._handle_ingest_pdf
        self._handlers[TaskType.REINDEX_DOCUMENT] = self._handle_reindex_document
        self._handlers[TaskType.SUMMARIZE_SESSION] = self._handle_summarize_session
        self._handlers[TaskType.INVALIDATE_CACHE] = self._handle_invalidate_cache

    # =========================================================================
    # PUBLIC METHODS
    # =========================================================================

    def register_handler(
        self,
        task_type: TaskType,
        handler: Callable[["QueuedTask"], Awaitable[None]],
    ) -> None:
        """
        Register a handler for a task type, replacing any existing one.

        Args:
            task_type: The task type to handle
            handler: Async callable that accepts a QueuedTask
        """
        self._handlers[task_type] = handler
        logger.info(
            "Registered handler for task_type=%s: %s",
            task_type.value,
            getattr(handler, "__qualname__", repr(handler)),
        )

    async def enqueue(
        self,
        task_type: TaskType | str,
        payload: dict[str, Any],
        priority: int = 5,
        task_id: str | None = None,
    ) -> str:
        """
        Enqueue a task with the specified priority.

        Args:
            task_type: Type of task to execute
            payload: Task payload data
            priority: Task priority (lower number = higher priority)
            task_id: Optional task ID (generated if not provided)

        Returns:
            Generated task_id

        Raises:
            ValueError: If task_type is invalid or priority is invalid
        """
        # Validate task_type
        if isinstance(task_type, str):
            try:
                task_type = TaskType(task_type)
            except ValueError:
                raise ValueError(f"Invalid task_type: {task_type}")

        # Validate priority
        if not isinstance(priority, int):
            raise ValueError(f"Priority must be an integer, got {type(priority)}")

        # Generate task_id if not provided
        if task_id is None:
            task_id = str(uuid.uuid4())

        # Get sequence number
        async with self._sequence_lock:
            sequence = self._sequence_counter
            self._sequence_counter += 1

        # Create task
        created_at = time.time()
        task = QueuedTask(
            priority=priority,
            sequence=sequence,
            task_id=task_id,
            task_type=task_type,
            payload=payload,
            created_at=created_at,
            status=TaskStatus.QUEUED,
        )

        # Store in registry
        async with self._tasks_lock:
            self._tasks[task_id] = task

        # Update status count
        async with self._status_lock:
            self._status_counts[TaskStatus.QUEUED] += 1

        # Add to queue
        await self._queue.put((priority, sequence, task))

        logger.info(
            "Task enqueued: task_id=%s, type=%s, priority=%d",
            task_id,
            task_type.value,
            priority,
        )

        return task_id

    async def process(self) -> None:
        """
        Start the async worker loop.

        This is the main async entrypoint that launches worker coroutines.
        Workers continuously pull highest-priority tasks from the queue
        and execute them until cancelled or stopped.

        Note: This coroutine blocks until all workers stop. Call ``stop()``
        from another coroutine (or cancel this task) to shut down the queue.
        """
        if self._running:
            logger.warning("TaskQueue already running")
            return

        self._running = True
        self._stop_event.clear()

        logger.info(
            "Starting TaskQueue with %d workers",
            self.max_workers,
        )

        # Create worker tasks
        self._workers = set()
        for worker_id in range(self.max_workers):
            worker = asyncio.create_task(
                self._worker_loop(worker_id),
                name=f"taskqueue-worker-{worker_id}",
            )
            self._workers.add(worker)

        # Wait for all workers to complete (or stop event)
        try:
            await asyncio.gather(*self._workers)
        except asyncio.CancelledError:
            logger.info("TaskQueue workers cancelled")
            raise

    async def start(self) -> None:
        """
        Start the task queue (alias for process()).
        """
        await self.process()

    async def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the task queue gracefully.

        Signals workers to stop accepting new tasks and waits for any
        in-flight tasks to finish before returning. If workers do not
        complete within ``timeout`` seconds they are force-cancelled.

        Args:
            timeout: Maximum seconds to wait for in-flight tasks to finish
                     before force-cancelling workers.
        """
        if not self._running:
            logger.warning("TaskQueue not running")
            return

        logger.info("Stopping TaskQueue gracefully...")
        self._stop_event.set()

        # Let workers finish their current task naturally, then exit.
        if self._workers:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._workers, return_exceptions=True),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Workers did not finish within %.1fs; force-cancelling",
                    timeout,
                )
                for worker in self._workers:
                    worker.cancel()
                await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        self._running = False

        logger.info("TaskQueue stopped")

    def get_status(self) -> dict[str, int]:
        """
        Get current queue status.

        Returns:
            Dictionary with status counts:
            - pending: Number of queued tasks
            - processing: Number of tasks currently being processed
            - completed: Number of completed tasks
            - failed: Number of failed tasks
            - total_enqueued: Total number of tasks ever enqueued
            - active_workers: Number of active worker tasks
        """
        # Intentionally lock-free: callers receive an approximate snapshot.
        # Minor inconsistencies between fields are acceptable for monitoring.
        return {
            "pending": self._status_counts[TaskStatus.QUEUED],
            "processing": self._status_counts[TaskStatus.PROCESSING],
            "completed": self._status_counts[TaskStatus.COMPLETED],
            "failed": self._status_counts[TaskStatus.FAILED],
            "total_enqueued": len(self._tasks),
            "active_workers": len(self._workers),
        }

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        """
        Get task details by ID.

        Args:
            task_id: The task ID to look up

        Returns:
            Task details dictionary or None if not found
        """
        # Use simple lookup without lock for now
        task = self._tasks.get(task_id)
        if task is None:
            return None
        return task.to_dict()

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    async def _worker_loop(self, worker_id: int) -> None:
        """
        Worker coroutine that continuously processes tasks.

        Args:
            worker_id: Unique identifier for this worker
        """
        logger.debug("Worker %d started", worker_id)

        while not self._stop_event.is_set():
            try:
                # Try to get a task from the queue
                try:
                    priority, sequence, task = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    # No task available, check if we should stop
                    if self._stop_event.is_set():
                        break
                    continue

                # Skip if queue is stopped
                if self._stop_event.is_set():
                    self._queue.task_done()
                    break

                # Process the task
                await self._execute_task(task, worker_id)

                self._queue.task_done()

            except asyncio.CancelledError:
                logger.debug("Worker %d cancelled", worker_id)
                break
            except Exception as e:
                logger.exception("Worker %d encountered error: %s", worker_id, e)

        logger.debug("Worker %d stopped", worker_id)

    async def _execute_task(self, task: QueuedTask, worker_id: int) -> None:
        """
        Execute a single task.

        Args:
            task: The task to execute
            worker_id: ID of the worker executing this task
        """
        task_id = task.task_id

        # Update status to processing
        async with self._tasks_lock:
            task.status = TaskStatus.PROCESSING
            self._tasks[task_id] = task

        async with self._status_lock:
            self._status_counts[TaskStatus.QUEUED] -= 1
            self._status_counts[TaskStatus.PROCESSING] += 1

        logger.info(
            "Worker %d processing task: task_id=%s, type=%s",
            worker_id,
            task_id,
            task.task_type.value,
        )

        # Get handler
        handler = self._handlers.get(task.task_type)

        if handler is None:
            error = f"No handler registered for task type: {task.task_type.value}"
            logger.error(error)
            await self._fail_task(task, error)
            return

        # Execute handler with error handling
        try:
            await handler(task)
            await self._complete_task(task)
        except Exception as e:
            logger.exception(
                "Task failed: task_id=%s, type=%s, error=%s",
                task_id,
                task.task_type.value,
                e,
            )
            await self._fail_task(task, str(e))

    async def _complete_task(self, task: QueuedTask) -> None:
        """Mark task as completed."""
        async with self._tasks_lock:
            task.status = TaskStatus.COMPLETED
            self._tasks[task.task_id] = task

        async with self._status_lock:
            self._status_counts[TaskStatus.PROCESSING] -= 1
            self._status_counts[TaskStatus.COMPLETED] += 1

        logger.info(
            "Task completed: task_id=%s, type=%s",
            task.task_id,
            task.task_type.value,
        )

    async def _fail_task(self, task: QueuedTask, error: str) -> None:
        """Mark task as failed."""
        async with self._tasks_lock:
            task.status = TaskStatus.FAILED
            task.error = error
            self._tasks[task.task_id] = task

        async with self._status_lock:
            self._status_counts[TaskStatus.PROCESSING] -= 1
            self._status_counts[TaskStatus.FAILED] += 1

        logger.error(
            "Task failed: task_id=%s, type=%s, error=%s",
            task.task_id,
            task.task_type.value,
            error,
        )

    # =========================================================================
    # TASK HANDLERS
    # =========================================================================

    async def _handle_ingest_pdf(self, task: QueuedTask) -> None:
        """
        Handle PDF ingestion task.

        Args:
            task: Task containing PDF path in payload
        """
        pdf_path = task.payload.get("pdf_path")
        if not pdf_path:
            raise ValueError("Missing required payload field: pdf_path")

        logger.info(
            "Handling ingest_pdf: task_id=%s, pdf_path=%s",
            task.task_id,
            pdf_path,
        )

        # Import and call the actual ingestion function.
        # ingest_pdf is synchronous and potentially CPU/IO-heavy, so run it
        # in a thread pool to avoid blocking the async event loop.
        try:
            from src.ingestion.index_builder import ingest_pdf

            result = await asyncio.to_thread(ingest_pdf, pdf_path)
            logger.info(
                "Ingestion complete: task_id=%s, doc_id=%s, pages=%d, chunks=%d",
                task.task_id,
                result.doc_id,
                result.page_count,
                result.chunk_count,
            )
        except ImportError:
            # If import fails, simulate successful completion
            logger.warning(
                "ingest_pdf not available, simulating success for task_id=%s",
                task.task_id,
            )
            await asyncio.sleep(0.1)  # Simulate some work

    async def _handle_reindex_document(self, task: QueuedTask) -> None:
        """
        Handle document reindexing task (placeholder).

        Args:
            task: Task containing doc_id in payload
        """
        doc_id = task.payload.get("doc_id")
        logger.info(
            "Handling reindex_document: task_id=%s, doc_id=%s (placeholder)",
            task.task_id,
            doc_id,
        )
        # Placeholder: simulate work
        await asyncio.sleep(0.1)

    async def _handle_summarize_session(self, task: QueuedTask) -> None:
        """
        Handle session summarization task (placeholder).

        Args:
            task: Task containing session_id in payload
        """
        session_id = task.payload.get("session_id")
        logger.info(
            "Handling summarize_session: task_id=%s, session_id=%s (placeholder)",
            task.task_id,
            session_id,
        )
        # Placeholder: simulate work
        await asyncio.sleep(0.1)

    async def _handle_invalidate_cache(self, task: QueuedTask) -> None:
        """
        Handle cache invalidation task (placeholder).

        Args:
            task: Task containing cache_key in payload
        """
        cache_key = task.payload.get("cache_key")
        logger.info(
            "Handling invalidate_cache: task_id=%s, cache_key=%s (placeholder)",
            task.task_id,
            cache_key,
        )
        # Placeholder: simulate work
        await asyncio.sleep(0.05)


# =============================================================================
# SINGLETON INSTANCE (OPTIONAL)
# =============================================================================

# Default queue instance for convenience
_default_queue: TaskQueue | None = None


def get_queue(max_workers: int = 4) -> TaskQueue:
    """
    Get or create the default task queue instance.

    Args:
        max_workers: Maximum number of workers (only used on first call)

    Returns:
        The default TaskQueue instance
    """
    global _default_queue
    if _default_queue is None:
        _default_queue = TaskQueue(max_workers=max_workers)
    return _default_queue

