"""
Unit tests for src/ingestion/watcher.py
"""

import heapq
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.ingestion.watcher import IngestionJob, IngestionWatcher, classify_priority

# =============================================================================
# classify_priority
# =============================================================================


class TestClassifyPriority:
    def test_p0_defect(self):
        assert classify_priority(Path("defect_report.pdf")) == ("P0", 0)

    def test_p0_rca(self):
        assert classify_priority(Path("RCA_incident.pdf")) == ("P0", 0)

    def test_p0_case_insensitive(self):
        assert classify_priority(Path("DEFECT_001.pdf")) == ("P0", 0)

    def test_p1_cli(self):
        assert classify_priority(Path("cli_reference.pdf")) == ("P1", 1)

    def test_p1_config(self):
        assert classify_priority(Path("config_guide.pdf")) == ("P1", 1)

    def test_p1_case_insensitive(self):
        assert classify_priority(Path("CLI_GUIDE.pdf")) == ("P1", 1)

    def test_p2_handbook(self):
        assert classify_priority(Path("employee_handbook.pdf")) == ("P2", 2)

    def test_p2_case_insensitive(self):
        assert classify_priority(Path("HANDBOOK.pdf")) == ("P2", 2)

    def test_p3_default(self):
        assert classify_priority(Path("release_notes.pdf")) == ("P3", 3)

    def test_p3_no_match(self):
        assert classify_priority(Path("quarterly_report.pdf")) == ("P3", 3)


# =============================================================================
# IngestionJob ordering (FIFO within same priority)
# =============================================================================


class TestIngestionJobOrdering:
    def _make_job(self, priority_num: int, counter: int) -> IngestionJob:
        return IngestionJob(
            priority_num=priority_num,
            counter=counter,
            file_path=Path("dummy.pdf"),
            priority_label=f"P{priority_num}",
            enqueue_time=time.monotonic(),
        )

    def test_lower_priority_num_sorts_first(self):
        high = self._make_job(0, 1)
        low = self._make_job(3, 2)
        assert high < low

    def test_same_priority_fifo_counter(self):
        first = self._make_job(1, 1)
        second = self._make_job(1, 2)
        assert first < second

    def test_heap_respects_priority_then_fifo(self):
        heap: list[IngestionJob] = []
        heapq.heappush(heap, self._make_job(3, 1))  # P3, arrived first
        heapq.heappush(heap, self._make_job(1, 2))  # P1
        heapq.heappush(heap, self._make_job(0, 3))  # P0
        heapq.heappush(heap, self._make_job(0, 4))  # P0, arrived second

        assert heapq.heappop(heap).priority_num == 0
        second = heapq.heappop(heap)
        assert second.priority_num == 0
        assert second.counter == 4  # FIFO: counter=4 after counter=3
        assert heapq.heappop(heap).priority_num == 1
        assert heapq.heappop(heap).priority_num == 3


# =============================================================================
# IngestionWatcher construction validation
# =============================================================================


class TestIngestionWatcherInit:
    def test_valid_directory(self, tmp_path):
        w = IngestionWatcher(tmp_path)
        assert w.watch_path == tmp_path.resolve()
        assert w.max_workers == 4
        assert w.debounce_seconds == 2.0

    def test_nonexistent_path_raises(self):
        with pytest.raises(FileNotFoundError):
            IngestionWatcher("/nonexistent/path/xyz")

    def test_file_path_raises(self, tmp_path):
        f = tmp_path / "some.pdf"
        f.write_bytes(b"%PDF")
        with pytest.raises(NotADirectoryError):
            IngestionWatcher(f)

    def test_custom_params(self, tmp_path):
        w = IngestionWatcher(tmp_path, max_workers=2, debounce_seconds=0.5)
        assert w.max_workers == 2
        assert w.debounce_seconds == 0.5


# =============================================================================
# enqueue_file filtering
# =============================================================================


class TestEnqueueFileFiltering:
    def _make_watcher(self, tmp_path):
        return IngestionWatcher(tmp_path, debounce_seconds=0.0)

    def test_non_pdf_ignored(self, tmp_path):
        w = self._make_watcher(tmp_path)
        w.enqueue_file(tmp_path / "document.txt")
        assert w._get_queue_depth() == 0

    def test_part_file_ignored(self, tmp_path):
        w = self._make_watcher(tmp_path)
        w.enqueue_file(tmp_path / "document.pdf.part")
        assert w._get_queue_depth() == 0

    def test_tmp_file_ignored(self, tmp_path):
        w = self._make_watcher(tmp_path)
        w.enqueue_file(tmp_path / "document.pdf.tmp")
        assert w._get_queue_depth() == 0

    def test_tilde_file_ignored(self, tmp_path):
        w = self._make_watcher(tmp_path)
        w.enqueue_file(tmp_path / "document.pdf~")
        assert w._get_queue_depth() == 0

    def test_valid_pdf_enqueued(self, tmp_path):
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF")
        w = self._make_watcher(tmp_path)
        # Patch _is_file_stable so we don't sleep in tests
        with patch.object(w, "_is_file_stable", return_value=True):
            w.enqueue_file(pdf)
        assert w._get_queue_depth() == 1


# =============================================================================
# Debounce behaviour
# =============================================================================


class TestDebounce:
    def test_second_event_within_window_ignored(self, tmp_path):
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF")
        w = IngestionWatcher(tmp_path, debounce_seconds=10.0)
        with patch.object(w, "_is_file_stable", return_value=True):
            w.enqueue_file(pdf)
            w.enqueue_file(pdf)  # within debounce window
        assert w._get_queue_depth() == 1

    def test_event_after_window_enqueued(self, tmp_path):
        pdf = tmp_path / "report.pdf"
        pdf.write_bytes(b"%PDF")
        w = IngestionWatcher(tmp_path, debounce_seconds=0.0)
        with patch.object(w, "_is_file_stable", return_value=True):
            w.enqueue_file(pdf)
            w.enqueue_file(pdf)  # debounce window is 0, should pass
        assert w._get_queue_depth() == 2


# =============================================================================
# File stability check
# =============================================================================


class TestIsFileStable:
    def test_stable_file_returns_true(self, tmp_path):
        pdf = tmp_path / "stable.pdf"
        pdf.write_bytes(b"%PDF-1.4 content")
        w = IngestionWatcher(tmp_path)
        # Use a very short poll interval to avoid slowing the test suite
        result = w._is_file_stable(pdf, poll_interval=0.05)
        assert result is True

    def test_missing_file_returns_false(self, tmp_path):
        w = IngestionWatcher(tmp_path)
        result = w._is_file_stable(tmp_path / "ghost.pdf", poll_interval=0.0)
        assert result is False

    def test_growing_file_returns_false(self, tmp_path):
        pdf = tmp_path / "growing.pdf"
        pdf.write_bytes(b"%PDF")
        w = IngestionWatcher(tmp_path)

        call_count = 0

        class _FakeStat:
            def __init__(self, size):
                self.st_size = size

        def fake_stat(self_path, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            return _FakeStat(call_count * 100)  # size grows each call

        with patch.object(Path, "stat", fake_stat):
            result = w._is_file_stable(pdf, poll_interval=0.0)
        assert result is False


# =============================================================================
# max_workers concurrency limit
# =============================================================================


class TestMaxWorkers:
    def test_no_more_than_max_workers_dispatched(self, tmp_path):
        """Verify the dispatcher never starts more concurrent jobs than max_workers."""
        max_workers = 2
        barrier = {"count": 0, "lock": __import__("threading").Lock()}
        peak = {"value": 0}

        def slow_ingest(file_path):
            with barrier["lock"]:
                barrier["count"] += 1
                if barrier["count"] > peak["value"]:
                    peak["value"] = barrier["count"]
            time.sleep(0.1)
            with barrier["lock"]:
                barrier["count"] -= 1

        pdfs = []
        for i in range(6):
            p = tmp_path / f"doc_{i}.pdf"
            p.write_bytes(b"%PDF")
            pdfs.append(p)

        w = IngestionWatcher(tmp_path, max_workers=max_workers, debounce_seconds=0.0)
        with (
            patch.object(w, "_is_file_stable", return_value=True),
            patch("src.ingestion.watcher.ingest_pdf", side_effect=lambda p: slow_ingest(p)),
        ):
            w.start()
            for p in pdfs:
                w.enqueue_file(p)
            time.sleep(1.0)
            w.stop()

        assert peak["value"] <= max_workers
