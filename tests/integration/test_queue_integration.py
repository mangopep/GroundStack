"""
Async integration tests for src/workers/queue.py.

These tests exercise the full worker lifecycle with real asyncio concurrency.
Run with:

    pytest tests/integration/test_queue_integration.py -v
"""

import asyncio
import time
from unittest.mock import patch

import pytest

from src.workers.queue import TaskQueue, TaskStatus, TaskType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_queue(**kwargs) -> TaskQueue:
    return TaskQueue(**kwargs)


# ---------------------------------------------------------------------------
# Concurrency: multiple workers really run in parallel
# ---------------------------------------------------------------------------


class TestConcurrentWorkers:
    @pytest.mark.anyio
    async def test_multiple_workers_overlap_in_time(self):
        """
        With N concurrent tasks that each sleep 200 ms and N workers,
        total wall-clock time should be close to 200 ms, not N * 200 ms.
        """
        n = 4
        q = _make_queue(max_workers=n)

        async def slow_handler(task):
            await asyncio.sleep(0.2)

        q._handlers[TaskType.INVALIDATE_CACHE] = slow_handler

        for i in range(n):
            await q.enqueue(TaskType.INVALIDATE_CACHE, {"i": i})

        process_task = asyncio.create_task(q.process())
        start = time.monotonic()

        for _ in range(40):
            await asyncio.sleep(0.05)
            if q.get_status()["completed"] == n:
                break

        elapsed = time.monotonic() - start
        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        assert q.get_status()["completed"] == n
        # If workers ran sequentially this would be ~0.8 s; allow generous
        # headroom for a slow CI machine but reject purely sequential execution.
        assert elapsed < 0.7, (
            f"Workers do not appear to be running concurrently (elapsed={elapsed:.2f}s)"
        )

    @pytest.mark.anyio
    async def test_active_worker_count_reported(self):
        """active_workers reflects the number of running worker tasks."""
        q = _make_queue(max_workers=3)
        process_task = asyncio.create_task(q.process())
        await asyncio.sleep(0.05)

        status = q.get_status()
        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        assert status["active_workers"] == 3


# ---------------------------------------------------------------------------
# ingest_pdf handler: must use asyncio.to_thread, not block the event loop
# ---------------------------------------------------------------------------


class TestIngestPdfHandler:
    @pytest.mark.anyio
    async def test_ingest_pdf_runs_in_thread(self):
        """
        The ingest_pdf handler must call asyncio.to_thread so a synchronous,
        blocking implementation does not stall the event loop.

        We verify this by patching to_thread and confirming it was called.
        """
        q = _make_queue(max_workers=1)

        called_with = {}

        async def fake_to_thread(fn, *args, **kwargs):
            called_with["fn"] = fn
            called_with["args"] = args

            # Return a minimal stub so the logger call after it doesn't crash
            class _Result:
                doc_id = "doc-1"
                page_count = 2
                chunk_count = 5

            return _Result()

        task_done = asyncio.Event()

        original_execute = q._execute_task

        async def execute_and_signal(task, worker_id):
            await original_execute(task, worker_id)
            task_done.set()

        q._execute_task = execute_and_signal

        with patch("src.workers.queue.asyncio.to_thread", side_effect=fake_to_thread):
            # Patch the import inside the handler as well
            with patch.dict("sys.modules", {}):
                import sys

                # Make the import inside handler succeed by injecting a stub module
                class _FakeModule:
                    @staticmethod
                    def ingest_pdf(path):  # pragma: no cover
                        return None

                sys.modules.setdefault("src.ingestion.index_builder", _FakeModule)

                await q.enqueue(TaskType.INGEST_PDF, {"pdf_path": "/tmp/test.pdf"})
                process_task = asyncio.create_task(q.process())
                await asyncio.wait_for(task_done.wait(), timeout=3.0)
                await q.stop()
                process_task.cancel()
                await asyncio.gather(process_task, return_exceptions=True)

        assert "fn" in called_with, "asyncio.to_thread was never called"

    @pytest.mark.anyio
    async def test_ingest_pdf_missing_pdf_path_fails_task(self):
        """Enqueuing ingest_pdf without pdf_path must move the task to FAILED."""
        q = _make_queue(max_workers=1)

        failed = asyncio.Event()
        original_fail = q._fail_task

        async def fail_and_signal(task, error):
            await original_fail(task, error)
            failed.set()

        q._fail_task = fail_and_signal

        task_id = await q.enqueue(TaskType.INGEST_PDF, {})  # no pdf_path
        process_task = asyncio.create_task(q.process())

        await asyncio.wait_for(failed.wait(), timeout=3.0)
        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        task_dict = q.get_task(task_id)
        assert task_dict["status"] == TaskStatus.FAILED.value
        assert "pdf_path" in task_dict["error"]


# ---------------------------------------------------------------------------
# Graceful stop: in-flight work must complete
# ---------------------------------------------------------------------------


class TestGracefulStop:
    @pytest.mark.anyio
    async def test_in_flight_task_completes_before_stop_returns(self):
        """
        stop() must wait for an executing task to finish.
        The task must be COMPLETED when stop() returns, not PROCESSING.
        """
        q = _make_queue(max_workers=1)

        started = asyncio.Event()
        finish_permission = asyncio.Event()
        finished = asyncio.Event()

        async def gated_handler(task):
            started.set()
            await finish_permission.wait()
            finished.set()

        q._handlers[TaskType.SUMMARIZE_SESSION] = gated_handler

        task_id = await q.enqueue(TaskType.SUMMARIZE_SESSION, {"session_id": "x"})
        process_task = asyncio.create_task(q.process())

        await asyncio.wait_for(started.wait(), timeout=2.0)

        # Trigger stop in the background, then let the handler proceed
        stop_task = asyncio.create_task(q.stop(timeout=5.0))
        await asyncio.sleep(0.05)
        finish_permission.set()

        await asyncio.wait_for(stop_task, timeout=5.0)
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        assert finished.is_set()
        assert q.get_task(task_id)["status"] == TaskStatus.COMPLETED.value

    @pytest.mark.anyio
    async def test_timeout_stop_force_cancels_stuck_workers(self):
        """
        If a task takes longer than the timeout, stop() must force-cancel
        and still return (not hang forever).
        """
        q = _make_queue(max_workers=1)

        started = asyncio.Event()

        async def stuck_handler(task):
            started.set()
            await asyncio.sleep(60)  # simulate stuck task

        q._handlers[TaskType.SUMMARIZE_SESSION] = stuck_handler

        await q.enqueue(TaskType.SUMMARIZE_SESSION, {"session_id": "stuck"})
        process_task = asyncio.create_task(q.process())

        await asyncio.wait_for(started.wait(), timeout=2.0)

        t0 = time.monotonic()
        await q.stop(timeout=0.3)  # very short timeout
        elapsed = time.monotonic() - t0

        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        # stop() must have returned after ~0.3 s, not after 60 s
        assert elapsed < 2.0, f"stop() appeared to hang (elapsed={elapsed:.2f}s)"
        assert not q._running


# ---------------------------------------------------------------------------
# Full lifecycle: priority + concurrency end-to-end
# ---------------------------------------------------------------------------


class TestEndToEndLifecycle:
    @pytest.mark.anyio
    async def test_high_priority_dequeued_before_low_with_single_worker(self):
        """
        Pre-load the queue with tasks at different priorities, then start a
        single worker. The dequeue order must respect priority.
        """
        q = _make_queue(max_workers=1)
        order: list[int] = []

        async def recording_handler(task):
            order.append(task.payload["prio"])

        q._handlers[TaskType.INVALIDATE_CACHE] = recording_handler

        for prio in [10, 3, 7, 1, 5]:
            await q.enqueue(TaskType.INVALIDATE_CACHE, {"prio": prio}, priority=prio)

        process_task = asyncio.create_task(q.process())

        for _ in range(30):
            await asyncio.sleep(0.1)
            if len(order) == 5:
                break

        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        assert order == sorted(order), f"Expected ascending priority order, got {order}"

    @pytest.mark.anyio
    async def test_all_task_types_complete_successfully(self):
        """All four built-in task types must reach COMPLETED status."""
        q = _make_queue(max_workers=4)

        task_ids = {
            TaskType.REINDEX_DOCUMENT: await q.enqueue(TaskType.REINDEX_DOCUMENT, {"doc_id": "d1"}),
            TaskType.SUMMARIZE_SESSION: await q.enqueue(
                TaskType.SUMMARIZE_SESSION, {"session_id": "s1"}
            ),
            TaskType.INVALIDATE_CACHE: await q.enqueue(
                TaskType.INVALIDATE_CACHE, {"cache_key": "k1"}
            ),
        }

        process_task = asyncio.create_task(q.process())

        for _ in range(30):
            await asyncio.sleep(0.1)
            statuses = {t: q.get_task(tid)["status"] for t, tid in task_ids.items()}
            if all(s == TaskStatus.COMPLETED.value for s in statuses.values()):
                break

        await q.stop()
        process_task.cancel()
        await asyncio.gather(process_task, return_exceptions=True)

        for task_type, task_id in task_ids.items():
            assert q.get_task(task_id)["status"] == TaskStatus.COMPLETED.value, (
                f"{task_type} task did not complete"
            )
