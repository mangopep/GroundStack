"""
Unit tests for src/workers/queue.py.

Each test maps to a specific contract the queue must honour. Run with:

    pytest tests/unit/test_queue.py -v
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.workers.queue import (
    QueuedTask,
    TaskQueue,
    TaskStatus,
    TaskType,
    get_queue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_queue(**kwargs) -> TaskQueue:
    """Return a fresh TaskQueue (not started)."""
    return TaskQueue(**kwargs)


# ---------------------------------------------------------------------------
# QueuedTask ordering
# ---------------------------------------------------------------------------


class TestQueuedTaskOrdering:
    """QueuedTask must sort by (priority, sequence) so the heap works correctly."""

    def test_lower_priority_number_sorts_first(self):
        high = QueuedTask(priority=1, sequence=0, task_id="a", task_type=TaskType.INVALIDATE_CACHE, payload={}, created_at=0.0)
        low = QueuedTask(priority=10, sequence=1, task_id="b", task_type=TaskType.INVALIDATE_CACHE, payload={}, created_at=0.0)
        assert high < low

    def test_same_priority_fifo_by_sequence(self):
        first = QueuedTask(priority=5, sequence=0, task_id="a", task_type=TaskType.INVALIDATE_CACHE, payload={}, created_at=0.0)
        second = QueuedTask(priority=5, sequence=1, task_id="b", task_type=TaskType.INVALIDATE_CACHE, payload={}, created_at=0.0)
        assert first < second

    def test_to_dict_has_expected_keys(self):
        task = QueuedTask(
            priority=3,
            sequence=0,
            task_id="abc",
            task_type=TaskType.INGEST_PDF,
            payload={"pdf_path": "/tmp/a.pdf"},
            created_at=1234.5,
        )
        d = task.to_dict()
        assert d["task_id"] == "abc"
        assert d["task_type"] == "ingest_pdf"
        assert d["priority"] == 3
        assert d["status"] == "queued"
        assert d["error"] is None


# ---------------------------------------------------------------------------
# TaskQueue construction
# ---------------------------------------------------------------------------


class TestTaskQueueConstruction:
    def test_invalid_max_workers_raises(self):
        with pytest.raises(ValueError, match="max_workers"):
            TaskQueue(max_workers=0)

    def test_negative_max_workers_raises(self):
        with pytest.raises(ValueError):
            TaskQueue(max_workers=-1)

    def test_valid_max_workers_stores_value(self):
        q = _make_queue(max_workers=3)
        assert q.max_workers == 3


# ---------------------------------------------------------------------------
# enqueue()
# ---------------------------------------------------------------------------


class TestEnqueue:
    @pytest.mark.anyio
    async def test_returns_task_id_string(self):
        q = _make_queue()
        task_id = await q.enqueue(TaskType.INVALIDATE_CACHE, {"cache_key": "x"})
        assert isinstance(task_id, str) and len(task_id) > 0

    @pytest.mark.anyio
    async def test_custom_task_id_honoured(self):
        q = _make_queue()
        task_id = await q.enqueue(TaskType.INVALIDATE_CACHE, {}, task_id="custom-123")
        assert task_id == "custom-123"

    @pytest.mark.anyio
    async def test_string_task_type_normalised(self):
        q = _make_queue()
        task_id = await q.enqueue("invalidate_cache", {})
        task = q.get_task(task_id)
        assert task["task_type"] == TaskType.INVALIDATE_CACHE.value

    @pytest.mark.anyio
    async def test_invalid_task_type_raises(self):
        q = _make_queue()
        with pytest.raises(ValueError, match="Invalid task_type"):
            await q.enqueue("not_a_real_type", {})

    @pytest.mark.anyio
    async def test_non_integer_priority_raises(self):
        q = _make_queue()
        with pytest.raises(ValueError, match="Priority must be an integer"):
            await q.enqueue(TaskType.INVALIDATE_CACHE, {}, priority=1.5)  # type: ignore[arg-type]

    @pytest.mark.anyio
    async def test_status_queued_after_enqueue(self):
        q = _make_queue()
        task_id = await q.enqueue(TaskType.INVALIDATE_CACHE, {"cache_key": "k"})
        task = q.get_task(task_id)
        assert task["status"] == TaskStatus.QUEUED.value

    @pytest.mark.anyio
    async def test_status_count_increments(self):
        q = _make_queue()
        await q.enqueue(TaskType.INVALIDATE_CACHE, {})
        await q.enqueue(TaskType.INVALIDATE_CACHE, {})
        assert q.get_status()["pending"] == 2

    @pytest.mark.anyio
    async def test_sequence_increases_monotonically(self):
        q = _make_queue()
        id1 = await q.enqueue(TaskType.INVALIDATE_CACHE, {})
        id2 = await q.enqueue(TaskType.INVALIDATE_CACHE, {})
        t1 = q._tasks[id1]
        t2 = q._tasks[id2]
        assert t1.sequence < t2.sequence


# ---------------------------------------------------------------------------
# get_task()
# ---------------------------------------------------------------------------


class TestGetTask:
    @pytest.mark.anyio
    async def test_unknown_id_returns_none(self):
        q = _make_queue()
        assert q.get_task("does-not-exist") is None

    @pytest.mark.anyio
    async def test_known_id_returns_dict(self):
        q = _make_queue()
        task_id = await q.enqueue(TaskType.SUMMARIZE_SESSION, {"session_id": "s1"})
        result = q.get_task(task_id)
        assert result is not None
        assert result["payload"]["session_id"] == "s1"


# ---------------------------------------------------------------------------
# Status transitions (process a single task with a mock handler)
# ---------------------------------------------------------------------------


class TestStatusTransitions:
    @pytest.mark.anyio
    async def test_task_reaches_completed(self):
        q = _make_queue(max_workers=1)

        completed = asyncio.Event()

        async def fast_handler(task):
            completed.set()

        q._handlers[TaskType.INVALIDATE_CACHE] = fast_handler

        task_id = await q.enqueue(TaskType.INVALIDATE_CACHE, {})
        process_task = asyncio.create_task(q.process())

        await asyncio.wait_for(completed.wait(), timeout=2.0)
        await asyncio.sleep(0.05)  # let _complete_task finish
        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        assert q.get_task(task_id)["status"] == TaskStatus.COMPLETED.value
        assert q.get_status()["completed"] == 1

    @pytest.mark.anyio
    async def test_task_reaches_failed_on_handler_exception(self):
        q = _make_queue(max_workers=1)

        failed = asyncio.Event()

        async def bad_handler(task):
            failed.set()
            raise RuntimeError("boom")

        q._handlers[TaskType.INVALIDATE_CACHE] = bad_handler

        task_id = await q.enqueue(TaskType.INVALIDATE_CACHE, {})
        process_task = asyncio.create_task(q.process())

        await asyncio.wait_for(failed.wait(), timeout=2.0)
        await asyncio.sleep(0.05)
        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        task_dict = q.get_task(task_id)
        assert task_dict["status"] == TaskStatus.FAILED.value
        assert "boom" in task_dict["error"]
        assert q.get_status()["failed"] == 1


# ---------------------------------------------------------------------------
# Failure isolation
# ---------------------------------------------------------------------------


class TestFailureIsolation:
    @pytest.mark.anyio
    async def test_one_failed_task_does_not_stop_queue(self):
        """A failing task must not prevent subsequent tasks from completing."""
        q = _make_queue(max_workers=1)

        order: list[str] = []

        async def handler(task):
            order.append(task.task_id)
            if task.task_id == "bad":
                raise RuntimeError("intentional failure")

        q._handlers[TaskType.INVALIDATE_CACHE] = handler

        await q.enqueue(TaskType.INVALIDATE_CACHE, {}, task_id="bad")
        await q.enqueue(TaskType.INVALIDATE_CACHE, {}, task_id="good")

        process_task = asyncio.create_task(q.process())
        # Wait until both tasks were attempted (queue size reaches 0)
        for _ in range(20):
            await asyncio.sleep(0.1)
            if q.get_status()["pending"] == 0 and q.get_status()["processing"] == 0:
                break

        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        assert q.get_task("bad")["status"] == TaskStatus.FAILED.value
        assert q.get_task("good")["status"] == TaskStatus.COMPLETED.value


# ---------------------------------------------------------------------------
# Priority ordering (end-to-end, single worker so ordering is deterministic)
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    @pytest.mark.anyio
    async def test_highest_priority_processed_first(self):
        """With a single worker, tasks must dequeue in priority order."""
        q = _make_queue(max_workers=1)

        dequeue_order: list[str] = []
        start_processing = asyncio.Event()

        async def tracking_handler(task):
            dequeue_order.append(task.payload["label"])

        q._handlers[TaskType.INVALIDATE_CACHE] = tracking_handler

        # Enqueue all tasks before starting the queue so the priority queue
        # is fully loaded when the worker picks up its first item.
        await q.enqueue(TaskType.INVALIDATE_CACHE, {"label": "low"}, priority=10, task_id="t-low")
        await q.enqueue(TaskType.INVALIDATE_CACHE, {"label": "high"}, priority=1, task_id="t-high")
        await q.enqueue(TaskType.INVALIDATE_CACHE, {"label": "mid"}, priority=5, task_id="t-mid")

        process_task = asyncio.create_task(q.process())

        for _ in range(30):
            await asyncio.sleep(0.1)
            if len(dequeue_order) == 3:
                break

        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        assert dequeue_order == ["high", "mid", "low"]

    @pytest.mark.anyio
    async def test_fifo_within_same_priority(self):
        """Tasks at equal priority must dequeue in insertion order."""
        q = _make_queue(max_workers=1)

        dequeue_order: list[str] = []

        async def tracking_handler(task):
            dequeue_order.append(task.payload["label"])

        q._handlers[TaskType.INVALIDATE_CACHE] = tracking_handler

        for label in ["first", "second", "third"]:
            await q.enqueue(TaskType.INVALIDATE_CACHE, {"label": label}, priority=5)

        process_task = asyncio.create_task(q.process())

        for _ in range(30):
            await asyncio.sleep(0.1)
            if len(dequeue_order) == 3:
                break

        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        assert dequeue_order == ["first", "second", "third"]


# ---------------------------------------------------------------------------
# stop() behaviour
# ---------------------------------------------------------------------------


class TestStop:
    @pytest.mark.anyio
    async def test_stop_when_not_running_is_safe(self):
        q = _make_queue()
        # Must not raise
        await q.stop()

    @pytest.mark.anyio
    async def test_running_flag_false_after_stop(self):
        q = _make_queue(max_workers=1)
        process_task = asyncio.create_task(q.process())
        await asyncio.sleep(0.05)
        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)
        assert not q._running

    @pytest.mark.anyio
    async def test_in_flight_task_allowed_to_finish(self):
        """stop() must not cancel a task that is currently executing."""
        q = _make_queue(max_workers=1)

        started = asyncio.Event()
        finished = asyncio.Event()

        async def slow_handler(task):
            started.set()
            await asyncio.sleep(0.3)
            finished.set()

        q._handlers[TaskType.SUMMARIZE_SESSION] = slow_handler

        task_id = await q.enqueue(TaskType.SUMMARIZE_SESSION, {"session_id": "s"})
        process_task = asyncio.create_task(q.process())

        await asyncio.wait_for(started.wait(), timeout=2.0)
        # Call stop while the task is still running
        await q.stop(timeout=5.0)
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        assert finished.is_set(), "Handler should have completed before stop returned"
        assert q.get_task(task_id)["status"] == TaskStatus.COMPLETED.value


# ---------------------------------------------------------------------------
# Singleton get_queue()
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_same_instance_returned(self):
        import src.workers.queue as _qmod

        _qmod._default_queue = None  # reset for test isolation
        q1 = get_queue(max_workers=2)
        q2 = get_queue(max_workers=8)  # max_workers ignored on second call
        assert q1 is q2

    def test_max_workers_only_respected_on_first_call(self):
        import src.workers.queue as _qmod

        _qmod._default_queue = None
        q = get_queue(max_workers=3)
        assert q.max_workers == 3
        _ = get_queue(max_workers=10)
        assert q.max_workers == 3  # unchanged
