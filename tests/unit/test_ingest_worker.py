"""
Unit tests for src/workers/ingest_worker.py.

Covers:
  - handler registration wires IngestWorker into TaskQueue
  - handle_ingest_task: success path (symlink, metadata, freshness)
  - handle_ingest_task: missing pdf_path raises ValueError
  - handle_ingest_task: re-raise on terminal failure so queue marks FAILED
  - handle_ingest_task: failed file moved to data/failed + error log written
  - _run_ingest_with_retries: succeeds on first attempt
  - _run_ingest_with_retries: retries on transient failure, succeeds eventually
  - _run_ingest_with_retries: exhausts all attempts and raises last error
  - _run_ingest_with_retries: exponential backoff between attempts
  - _create_processed_symlink: creates symlink, replaces existing symlink
  - _move_to_failed: moves file, avoids overwrite with timestamp suffix
  - _write_error_log: writes log alongside failed file with traceback
  - _document_exists: returns True/False; returns False on DB error
  - _update_document_status: skips when doc_id is None
  - _update_document_status: updates row; inserts when row missing
  - _update_document_status: handles UndefinedColumn gracefully
  - _notify_freshness_invalidator: swallows ImportError (no module)
  - _notify_freshness_invalidator: swallows arbitrary runtime exception
  - run_forever: calls register() then queue.process()
  - stop: delegates to queue.stop()

Run with:
    pytest tests/unit/test_ingest_worker.py -v
"""

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from src.workers.ingest_worker import IngestWorker, _notify_freshness_invalidator
from src.workers.queue import QueuedTask, TaskQueue, TaskStatus, TaskType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MODULE = "src.workers.ingest_worker"


def _make_task(
    pdf_path: str | None = "/tmp/test.pdf",
    doc_id: str | None = None,
    reingest: bool = False,
    task_id: str = "task-001",
) -> QueuedTask:
    """Return a minimal INGEST_PDF QueuedTask."""
    payload: dict = {}
    if pdf_path is not None:
        payload["pdf_path"] = pdf_path
    if doc_id is not None:
        payload["doc_id"] = doc_id
    if reingest:
        payload["reingest"] = True
    return QueuedTask(
        priority=5,
        sequence=0,
        task_id=task_id,
        task_type=TaskType.INGEST_PDF,
        payload=payload,
        created_at=0.0,
        status=TaskStatus.QUEUED,
    )


def _make_result(doc_id: str = "doc-abc", page_count: int = 3, chunk_count: int = 10):
    """Return a fake IngestResult-like namespace."""
    return SimpleNamespace(doc_id=doc_id, page_count=page_count, chunk_count=chunk_count)


def _make_worker(tmp_path: Path, queue: TaskQueue | None = None, max_attempts: int = 3) -> IngestWorker:
    """Return an IngestWorker that writes under tmp_path."""
    return IngestWorker(
        queue=queue,
        max_attempts=max_attempts,
        failed_dir=tmp_path / "failed",
        processed_dir=tmp_path / "processed",
    )


# ===========================================================================
# Handler registration
# ===========================================================================


class TestHandlerRegistration:
    def test_register_sets_ingest_pdf_handler(self, tmp_path):
        queue = TaskQueue(max_workers=1)
        worker = _make_worker(tmp_path, queue=queue)

        worker.register()

        # Bound methods are re-created on each attribute access, so compare
        # by underlying function and self, not by identity.
        registered = queue._handlers[TaskType.INGEST_PDF]
        assert registered.__func__ is IngestWorker.handle_ingest_task
        assert registered.__self__ is worker

    def test_run_forever_calls_register_then_process(self, tmp_path):
        """run_forever() must register the handler before starting the queue."""
        queue = MagicMock(spec=TaskQueue)
        queue.process = AsyncMock()
        worker = _make_worker(tmp_path, queue=queue)

        asyncio.get_event_loop().run_until_complete(worker.run_forever())

        queue.register_handler.assert_called_once_with(
            TaskType.INGEST_PDF, worker.handle_ingest_task
        )
        queue.process.assert_awaited_once()

    def test_run_forever_swallows_cancelled_error(self, tmp_path):
        """CancelledError from queue.process() must not propagate out."""
        queue = MagicMock(spec=TaskQueue)
        queue.process = AsyncMock(side_effect=asyncio.CancelledError)
        worker = _make_worker(tmp_path, queue=queue)

        # Should not raise
        asyncio.get_event_loop().run_until_complete(worker.run_forever())


# ===========================================================================
# stop()
# ===========================================================================


class TestStop:
    def test_stop_delegates_to_queue_stop(self, tmp_path):
        queue = MagicMock(spec=TaskQueue)
        queue.stop = AsyncMock()
        worker = _make_worker(tmp_path, queue=queue)

        asyncio.get_event_loop().run_until_complete(worker.stop(timeout=5.0))

        queue.stop.assert_awaited_once_with(timeout=5.0)


# ===========================================================================
# handle_ingest_task — success path
# ===========================================================================


class TestHandleIngestTaskSuccess:
    @pytest.fixture()
    def pdf_file(self, tmp_path) -> Path:
        p = tmp_path / "corpus" / "sample.pdf"
        p.parent.mkdir(parents=True)
        p.write_bytes(b"%PDF-1.4 fake")
        return p

    @pytest.mark.anyio
    async def test_success_creates_symlink(self, tmp_path, pdf_file):
        worker = _make_worker(tmp_path)
        result = _make_result(doc_id="doc-xyz")
        task = _make_task(pdf_path=str(pdf_file))

        with (
            patch.object(worker, "_run_ingest_with_retries", AsyncMock(return_value=result)),
            patch.object(worker, "_update_document_status", AsyncMock()),
            patch.object(worker, "_document_exists", return_value=False),
        ):
            await worker.handle_ingest_task(task)

        symlink = tmp_path / "processed" / "doc-xyz.pdf"
        assert symlink.is_symlink()
        assert symlink.resolve() == pdf_file.resolve()

    @pytest.mark.anyio
    async def test_success_updates_status_done(self, tmp_path, pdf_file):
        worker = _make_worker(tmp_path)
        result = _make_result(doc_id="doc-xyz")
        task = _make_task(pdf_path=str(pdf_file))
        update_mock = AsyncMock()

        with (
            patch.object(worker, "_run_ingest_with_retries", AsyncMock(return_value=result)),
            patch.object(worker, "_update_document_status", update_mock),
            patch.object(worker, "_document_exists", return_value=False),
        ):
            await worker.handle_ingest_task(task)

        update_mock.assert_awaited_once_with("doc-xyz", "done", None)

    @pytest.mark.anyio
    async def test_success_calls_freshness_on_reingestion(self, tmp_path, pdf_file):
        worker = _make_worker(tmp_path)
        result = _make_result(doc_id="doc-xyz")
        # reingest=True in payload → freshness must be notified
        task = _make_task(pdf_path=str(pdf_file), reingest=True)

        with (
            patch.object(worker, "_run_ingest_with_retries", AsyncMock(return_value=result)),
            patch.object(worker, "_update_document_status", AsyncMock()),
            patch.object(worker, "_document_exists", return_value=False),
            patch(f"{MODULE}._notify_freshness_invalidator") as notify_mock,
        ):
            await worker.handle_ingest_task(task)

        notify_mock.assert_called_once_with("doc-xyz")

    @pytest.mark.anyio
    async def test_success_no_freshness_on_first_ingest(self, tmp_path, pdf_file):
        worker = _make_worker(tmp_path)
        result = _make_result(doc_id="doc-new")
        task = _make_task(pdf_path=str(pdf_file))

        with (
            patch.object(worker, "_run_ingest_with_retries", AsyncMock(return_value=result)),
            patch.object(worker, "_update_document_status", AsyncMock()),
            patch.object(worker, "_document_exists", return_value=False),
            patch(f"{MODULE}._notify_freshness_invalidator") as notify_mock,
        ):
            await worker.handle_ingest_task(task)

        notify_mock.assert_not_called()

    @pytest.mark.anyio
    async def test_existing_doc_id_in_db_triggers_reingestion(self, tmp_path, pdf_file):
        worker = _make_worker(tmp_path)
        result = _make_result(doc_id="doc-existing")
        # doc_id present in payload AND _document_exists() returns True
        task = _make_task(pdf_path=str(pdf_file), doc_id="doc-existing")

        with (
            patch.object(worker, "_run_ingest_with_retries", AsyncMock(return_value=result)),
            patch.object(worker, "_update_document_status", AsyncMock()),
            patch.object(worker, "_document_exists", return_value=True),
            patch(f"{MODULE}._notify_freshness_invalidator") as notify_mock,
        ):
            await worker.handle_ingest_task(task)

        notify_mock.assert_called_once_with("doc-existing")


# ===========================================================================
# handle_ingest_task — failure path
# ===========================================================================


class TestHandleIngestTaskFailure:
    @pytest.mark.anyio
    async def test_missing_pdf_path_raises_value_error(self, tmp_path):
        worker = _make_worker(tmp_path)
        task = _make_task(pdf_path=None)

        with pytest.raises(ValueError, match="pdf_path"):
            await worker.handle_ingest_task(task)

    @pytest.mark.anyio
    async def test_terminal_failure_reraises(self, tmp_path):
        """The handler must re-raise so the queue marks the task FAILED."""
        worker = _make_worker(tmp_path)
        task = _make_task()
        boom = RuntimeError("pipeline exploded")

        with (
            patch.object(worker, "_run_ingest_with_retries", AsyncMock(side_effect=boom)),
            patch.object(worker, "_update_document_status", AsyncMock()),
            patch.object(worker, "_move_to_failed", AsyncMock()),
            patch.object(worker, "_document_exists", return_value=False),
        ):
            with pytest.raises(RuntimeError, match="pipeline exploded"):
                await worker.handle_ingest_task(task)

    @pytest.mark.anyio
    async def test_terminal_failure_updates_status_failed(self, tmp_path):
        worker = _make_worker(tmp_path)
        task = _make_task(doc_id="doc-known")
        boom = RuntimeError("disk full")
        update_mock = AsyncMock()

        with (
            patch.object(worker, "_run_ingest_with_retries", AsyncMock(side_effect=boom)),
            patch.object(worker, "_update_document_status", update_mock),
            patch.object(worker, "_move_to_failed", AsyncMock()),
            patch.object(worker, "_document_exists", return_value=False),
        ):
            with pytest.raises(RuntimeError):
                await worker.handle_ingest_task(task)

        update_mock.assert_awaited_once_with("doc-known", "failed", "disk full")

    @pytest.mark.anyio
    async def test_terminal_failure_moves_file_to_failed(self, tmp_path):
        worker = _make_worker(tmp_path)
        task = _make_task()
        boom = RuntimeError("broken PDF")
        move_mock = AsyncMock()

        with (
            patch.object(worker, "_run_ingest_with_retries", AsyncMock(side_effect=boom)),
            patch.object(worker, "_update_document_status", AsyncMock()),
            patch.object(worker, "_move_to_failed", move_mock),
            patch.object(worker, "_document_exists", return_value=False),
        ):
            with pytest.raises(RuntimeError):
                await worker.handle_ingest_task(task)

        move_mock.assert_awaited_once()
        call_args = move_mock.call_args
        assert call_args.args[0] == Path("/tmp/test.pdf")
        assert call_args.args[1] is boom


# ===========================================================================
# _run_ingest_with_retries
# ===========================================================================


class TestRunIngestWithRetries:
    @pytest.mark.anyio
    async def test_succeeds_first_attempt(self, tmp_path):
        worker = _make_worker(tmp_path, max_attempts=3)
        result = _make_result()

        with patch(f"{MODULE}.asyncio.to_thread", AsyncMock(return_value=result)):
            with patch(f"src.ingestion.index_builder.ingest_pdf"):
                # to_thread is patched directly so the import inside the loop
                # doesn't matter — patch it at the asyncio level
                actual = await worker._run_ingest_with_retries(Path("/tmp/a.pdf"), {})

        assert actual is result

    @pytest.mark.anyio
    async def test_retries_on_transient_failure(self, tmp_path):
        """Fails twice, succeeds on third attempt."""
        worker = _make_worker(tmp_path, max_attempts=3)
        result = _make_result()
        call_count = 0

        async def _fake_to_thread(fn, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OSError("transient")
            return result

        with (
            patch(f"{MODULE}.asyncio.to_thread", side_effect=_fake_to_thread),
            patch(f"{MODULE}.asyncio.sleep", AsyncMock()),
        ):
            actual = await worker._run_ingest_with_retries(Path("/tmp/a.pdf"), {})

        assert actual is result
        assert call_count == 3

    @pytest.mark.anyio
    async def test_exhausts_attempts_and_raises_last_error(self, tmp_path):
        worker = _make_worker(tmp_path, max_attempts=3)
        errors = [OSError("e1"), OSError("e2"), OSError("e3")]
        idx = 0

        async def _always_fail(fn, *args, **kwargs):
            nonlocal idx
            err = errors[idx]
            idx += 1
            raise err

        with (
            patch(f"{MODULE}.asyncio.to_thread", side_effect=_always_fail),
            patch(f"{MODULE}.asyncio.sleep", AsyncMock()),
        ):
            with pytest.raises(OSError, match="e3"):
                await worker._run_ingest_with_retries(Path("/tmp/a.pdf"), {})

    @pytest.mark.anyio
    async def test_exponential_backoff_between_attempts(self, tmp_path):
        """asyncio.sleep must be called with 1, 2 seconds (3 attempts → 2 gaps)."""
        worker = _make_worker(tmp_path, max_attempts=3)
        sleep_mock = AsyncMock()
        idx = 0

        async def _fail_twice(fn, *args, **kwargs):
            nonlocal idx
            idx += 1
            if idx < 3:
                raise OSError("transient")
            return _make_result()

        with (
            patch(f"{MODULE}.asyncio.to_thread", side_effect=_fail_twice),
            patch(f"{MODULE}.asyncio.sleep", sleep_mock),
        ):
            await worker._run_ingest_with_retries(Path("/tmp/a.pdf"), {})

        assert sleep_mock.await_count == 2
        sleep_mock.assert_any_await(1)  # 2^0
        sleep_mock.assert_any_await(2)  # 2^1

    @pytest.mark.anyio
    async def test_no_sleep_after_last_attempt(self, tmp_path):
        """No sleep after the final failed attempt."""
        worker = _make_worker(tmp_path, max_attempts=2)
        sleep_mock = AsyncMock()

        async def _always_fail(fn, *args, **kwargs):
            raise OSError("always")

        with (
            patch(f"{MODULE}.asyncio.to_thread", side_effect=_always_fail),
            patch(f"{MODULE}.asyncio.sleep", sleep_mock),
        ):
            with pytest.raises(OSError):
                await worker._run_ingest_with_retries(Path("/tmp/a.pdf"), {})

        # Only 1 sleep between attempt 1 and attempt 2; no sleep after attempt 2
        assert sleep_mock.await_count == 1


# ===========================================================================
# _create_processed_symlink
# ===========================================================================


class TestCreateProcessedSymlink:
    @pytest.mark.anyio
    async def test_creates_symlink_pointing_to_source(self, tmp_path):
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"fake pdf")
        worker = _make_worker(tmp_path)

        await worker._create_processed_symlink(pdf, "doc-001")

        symlink = tmp_path / "processed" / "doc-001.pdf"
        assert symlink.is_symlink()
        assert symlink.resolve() == pdf.resolve()

    @pytest.mark.anyio
    async def test_replaces_existing_symlink(self, tmp_path):
        pdf = tmp_path / "sample.pdf"
        pdf.write_bytes(b"fake pdf")
        worker = _make_worker(tmp_path)

        # Create initial symlink
        await worker._create_processed_symlink(pdf, "doc-001")

        # Create a second PDF and overwrite the symlink
        pdf2 = tmp_path / "sample2.pdf"
        pdf2.write_bytes(b"fake pdf 2")
        await worker._create_processed_symlink(pdf2, "doc-001")

        symlink = tmp_path / "processed" / "doc-001.pdf"
        assert symlink.is_symlink()
        assert symlink.resolve() == pdf2.resolve()

    @pytest.mark.anyio
    async def test_symlink_failure_does_not_raise(self, tmp_path):
        """A broken os.symlink call must be swallowed (best-effort)."""
        worker = _make_worker(tmp_path)

        with patch("os.symlink", side_effect=OSError("permission denied")):
            # Must not raise
            await worker._create_processed_symlink(Path("/tmp/x.pdf"), "doc-001")


# ===========================================================================
# _move_to_failed
# ===========================================================================


class TestMoveToFailed:
    @pytest.mark.anyio
    async def test_moves_file_to_failed_dir(self, tmp_path):
        pdf = tmp_path / "broken.pdf"
        pdf.write_bytes(b"bad pdf")
        worker = _make_worker(tmp_path)
        err = ValueError("corrupt file")

        await worker._move_to_failed(pdf, err)

        assert (tmp_path / "failed" / "broken.pdf").exists()
        assert not pdf.exists()

    @pytest.mark.anyio
    async def test_avoids_overwrite_with_timestamp_suffix(self, tmp_path):
        pdf1 = tmp_path / "corpus" / "broken.pdf"
        pdf1.parent.mkdir()
        pdf1.write_bytes(b"pdf 1")
        pdf2 = tmp_path / "corpus2" / "broken.pdf"
        pdf2.parent.mkdir()
        pdf2.write_bytes(b"pdf 2")

        worker = _make_worker(tmp_path)
        err = ValueError("bad")

        await worker._move_to_failed(pdf1, err)
        await worker._move_to_failed(pdf2, err)

        # Both files must be present in failed/
        files = list((tmp_path / "failed").glob("broken*.pdf"))
        assert len(files) == 2

    @pytest.mark.anyio
    async def test_writes_error_log_alongside_file(self, tmp_path):
        pdf = tmp_path / "broken.pdf"
        pdf.write_bytes(b"bad pdf")
        worker = _make_worker(tmp_path)
        err = ValueError("something went wrong")

        await worker._move_to_failed(pdf, err)

        logs = list((tmp_path / "failed").glob("broken.pdf.error.log"))
        assert len(logs) == 1
        content = logs[0].read_text()
        assert "ValueError" in content
        assert "something went wrong" in content


# ===========================================================================
# _write_error_log
# ===========================================================================


class TestWriteErrorLog:
    @pytest.mark.anyio
    async def test_log_contains_required_fields(self, tmp_path):
        failed = tmp_path / "failed" / "broken.pdf"
        failed.parent.mkdir(parents=True)
        failed.write_bytes(b"")

        worker = _make_worker(tmp_path)
        err = RuntimeError("disk full")

        await worker._write_error_log(failed, Path("/original/broken.pdf"), err)

        log = failed.with_suffix(failed.suffix + ".error.log")
        assert log.exists()
        text = log.read_text()
        assert "RuntimeError" in text
        assert "disk full" in text
        assert "/original/broken.pdf" in text

    @pytest.mark.anyio
    async def test_write_failure_does_not_propagate(self, tmp_path):
        worker = _make_worker(tmp_path)
        mock_path = MagicMock(spec=Path)
        mock_path.with_suffix.return_value.write_text.side_effect = PermissionError("denied")

        # Must not raise
        await worker._write_error_log(mock_path, Path("/tmp/x.pdf"), ValueError("err"))


# ===========================================================================
# _document_exists
# ===========================================================================


class TestDocumentExists:
    def test_returns_false_for_none_doc_id(self, tmp_path):
        worker = _make_worker(tmp_path)
        assert worker._document_exists(None) is False  # type: ignore[arg-type]

    def test_returns_false_for_empty_string(self, tmp_path):
        worker = _make_worker(tmp_path)
        assert worker._document_exists("") is False

    def test_returns_true_when_row_found(self, tmp_path):
        worker = _make_worker(tmp_path)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1,)
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("psycopg.connect", return_value=mock_conn):
            assert worker._document_exists("doc-abc") is True

    def test_returns_false_when_no_row(self, tmp_path):
        worker = _make_worker(tmp_path)
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("psycopg.connect", return_value=mock_conn):
            assert worker._document_exists("doc-abc") is False

    def test_returns_false_on_db_error(self, tmp_path):
        worker = _make_worker(tmp_path)
        with patch("psycopg.connect", side_effect=OSError("connection refused")):
            assert worker._document_exists("doc-abc") is False


# ===========================================================================
# _update_document_status
# ===========================================================================


class TestUpdateDocumentStatus:
    @pytest.mark.anyio
    async def test_skips_when_doc_id_is_none(self, tmp_path):
        worker = _make_worker(tmp_path)
        with patch("psycopg.connect") as mock_connect:
            await worker._update_document_status(None, "done", None)
        mock_connect.assert_not_called()

    @pytest.mark.anyio
    async def test_updates_existing_row(self, tmp_path):
        worker = _make_worker(tmp_path)
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 1  # row was updated
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("psycopg.connect", return_value=mock_conn):
            await worker._update_document_status("doc-abc", "done", None)

        mock_cursor.execute.assert_called()
        mock_conn.commit.assert_called_once()

    @pytest.mark.anyio
    async def test_inserts_when_row_missing(self, tmp_path):
        worker = _make_worker(tmp_path)
        mock_cursor = MagicMock()
        mock_cursor.rowcount = 0  # UPDATE found nothing → INSERT expected
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("psycopg.connect", return_value=mock_conn):
            await worker._update_document_status("doc-new", "done", None)

        # execute called twice: once for UPDATE, once for INSERT
        assert mock_cursor.execute.call_count == 2

    @pytest.mark.anyio
    async def test_handles_undefined_column_gracefully(self, tmp_path):
        """If the status column is missing, rollback and continue silently."""
        import psycopg.errors

        worker = _make_worker(tmp_path)
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = psycopg.errors.UndefinedColumn("no column")
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        mock_conn.__enter__ = lambda s: mock_conn
        mock_conn.__exit__ = MagicMock(return_value=False)

        with patch("psycopg.connect", return_value=mock_conn):
            # Must not raise
            await worker._update_document_status("doc-abc", "done", None)

        mock_conn.rollback.assert_called_once()

    @pytest.mark.anyio
    async def test_swallows_general_db_error(self, tmp_path):
        worker = _make_worker(tmp_path)
        with patch("psycopg.connect", side_effect=OSError("connection refused")):
            # Must not raise
            await worker._update_document_status("doc-abc", "done", None)


# ===========================================================================
# _notify_freshness_invalidator
# ===========================================================================


class TestNotifyFreshnessInvalidator:
    def test_silent_when_module_not_installed(self):
        with patch.dict("sys.modules", {"src.ingestion.freshness": None}):
            # ImportError path — must not raise
            _notify_freshness_invalidator("doc-abc")

    def test_calls_invalidate_freshness_when_available(self):
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"src.ingestion.freshness": mock_module}):
            _notify_freshness_invalidator("doc-abc")
        mock_module.invalidate_freshness.assert_called_once_with("doc-abc")

    def test_swallows_runtime_exception_from_invalidator(self):
        mock_module = MagicMock()
        mock_module.invalidate_freshness.side_effect = RuntimeError("redis down")
        with patch.dict("sys.modules", {"src.ingestion.freshness": mock_module}):
            # Must not raise — freshness invalidation is best-effort
            _notify_freshness_invalidator("doc-abc")


# ===========================================================================
# IngestWorker.__init__ / directory creation
# ===========================================================================


class TestInit:
    def test_creates_failed_and_processed_dirs(self, tmp_path):
        worker = _make_worker(tmp_path)
        assert (tmp_path / "failed").is_dir()
        assert (tmp_path / "processed").is_dir()

    def test_lazy_queue_creation(self, tmp_path):
        """queue property must call get_queue() only when first accessed."""
        worker = _make_worker(tmp_path, queue=None)
        fake_queue = MagicMock(spec=TaskQueue)

        with patch(f"{MODULE}.get_queue", return_value=fake_queue) as mock_get:
            q = worker.queue
            _ = worker.queue  # second access must NOT call get_queue again

        mock_get.assert_called_once()
        assert q is fake_queue
