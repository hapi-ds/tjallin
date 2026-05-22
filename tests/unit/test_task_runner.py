"""Unit tests for task execution wrapper."""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

from tj_utils.task_runner import (
    MAX_STDERR_CHARS,
    calculate_elapsed_time,
    check_lock_file,
    create_lock_file,
    format_task_failure_log,
    format_task_overlap_log,
    format_task_success_log,
    format_task_timeout_log,
    parse_lock_start_time,
    remove_lock_file,
    truncate_stderr,
)


class TestTruncateStderr:
    """Tests for truncate_stderr function."""

    def test_short_string_unchanged(self):
        result = truncate_stderr("short error")
        assert result == "short error"

    def test_exact_limit_unchanged(self):
        text = "x" * MAX_STDERR_CHARS
        result = truncate_stderr(text)
        assert len(result) == MAX_STDERR_CHARS

    def test_over_limit_truncated(self):
        text = "x" * 2000
        result = truncate_stderr(text)
        assert len(result) == MAX_STDERR_CHARS

    def test_empty_string(self):
        result = truncate_stderr("")
        assert result == ""

    def test_custom_max_chars(self):
        result = truncate_stderr("hello world", max_chars=5)
        assert result == "hello"


class TestLockFile:
    """Tests for lock file operations."""

    def test_check_no_lock_file(self):
        exists, content = check_lock_file("/tmp/nonexistent_lock_12345.lock")
        assert exists is False
        assert content is None

    def test_create_and_check_lock_file(self):
        with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
            lock_path = f.name

        try:
            # Remove the temp file so create_lock_file creates it fresh
            Path(lock_path).unlink()

            create_lock_file(lock_path)
            exists, content = check_lock_file(lock_path)
            assert exists is True
            assert "PID=" in content
            assert "STARTED=" in content
        finally:
            remove_lock_file(lock_path)

    def test_remove_lock_file(self):
        with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
            lock_path = f.name

        Path(lock_path).unlink()
        create_lock_file(lock_path)
        assert Path(lock_path).exists()

        remove_lock_file(lock_path)
        assert not Path(lock_path).exists()

    def test_remove_nonexistent_lock_file(self):
        # Should not raise
        remove_lock_file("/tmp/nonexistent_lock_99999.lock")


class TestParseLockStartTime:
    """Tests for parse_lock_start_time function."""

    def test_valid_content(self):
        content = "PID=1234 STARTED=2024-01-15T10:30:00+00:00"
        result = parse_lock_start_time(content)
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_invalid_content(self):
        result = parse_lock_start_time("garbage data")
        assert result is None

    def test_empty_content(self):
        result = parse_lock_start_time("")
        assert result is None


class TestCalculateElapsedTime:
    """Tests for calculate_elapsed_time function."""

    def test_elapsed_time_positive(self):
        # Use a time in the past
        past = datetime(2020, 1, 1, tzinfo=timezone.utc)
        elapsed = calculate_elapsed_time(past)
        assert elapsed > 0

    def test_elapsed_time_recent(self):
        # A very recent time should give a small positive elapsed
        from datetime import timedelta

        recent = datetime.now(timezone.utc) - timedelta(seconds=5)
        elapsed = calculate_elapsed_time(recent)
        assert 4 <= elapsed <= 10


class TestOverlapDetectionFlow:
    """Tests for the full overlap detection scenario.

    Validates that when a lock file exists with a valid start time,
    the overlap detection flow correctly identifies the running task
    and produces the appropriate warning log.
    """

    def test_overlap_detected_when_lock_exists(self):
        """Lock file present → parse start time → calculate elapsed → format overlap log."""
        with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
            lock_path = f.name

        try:
            Path(lock_path).unlink()
            create_lock_file(lock_path)

            # Simulate overlap detection flow
            exists, content = check_lock_file(lock_path)
            assert exists is True
            assert content is not None

            start_time = parse_lock_start_time(content)
            assert start_time is not None

            elapsed = calculate_elapsed_time(start_time)
            assert elapsed >= 0

            ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
            log = format_task_overlap_log("tj-cron", "compile", elapsed, timestamp=ts)
            assert "skipped" in log
            assert "compile" in log
            assert "[WARNING]" in log
        finally:
            remove_lock_file(lock_path)

    def test_no_overlap_when_lock_absent(self):
        """No lock file → no overlap, task should proceed."""
        exists, content = check_lock_file("/tmp/nonexistent_overlap_test.lock")
        assert exists is False
        assert content is None

    def test_lock_cleanup_after_task(self):
        """Lock file is removed after task execution completes."""
        with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
            lock_path = f.name

        try:
            Path(lock_path).unlink()
            create_lock_file(lock_path)
            assert Path(lock_path).exists()

            # Simulate task completion → cleanup
            remove_lock_file(lock_path)
            assert not Path(lock_path).exists()

            # Verify no overlap detected after cleanup
            exists, _ = check_lock_file(lock_path)
            assert exists is False
        finally:
            # Safety cleanup
            remove_lock_file(lock_path)

    def test_lock_content_is_parseable(self):
        """Lock file created by create_lock_file is parseable by parse_lock_start_time."""
        with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as f:
            lock_path = f.name

        try:
            Path(lock_path).unlink()
            create_lock_file(lock_path)

            _, content = check_lock_file(lock_path)
            start_time = parse_lock_start_time(content)
            assert start_time is not None
            assert start_time.tzinfo is not None  # Should be timezone-aware
        finally:
            remove_lock_file(lock_path)


class TestTimeoutHandling:
    """Tests for timeout-related logging behavior."""

    def test_timeout_log_contains_timeout_value(self):
        """Timeout log includes the configured timeout duration."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        log = format_task_timeout_log("tj-cron", "compile", 300, timestamp=ts)
        assert "300s" in log
        assert "timed out" in log

    def test_timeout_log_with_custom_timeout(self):
        """Timeout log works with non-default timeout values."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        log = format_task_timeout_log("tj-cron", "collect-timesheets", 600, timestamp=ts)
        assert "600s" in log
        assert "collect-timesheets" in log
        assert "[ERROR]" in log

    def test_timeout_log_with_short_timeout(self):
        """Timeout log works with very short timeout values."""
        log = format_task_timeout_log("tj-cron", "quick-task", 10)
        assert "10s" in log
        assert "quick-task" in log


class TestFormatTaskLogs:
    """Tests for task log formatting functions."""

    def test_success_log(self):
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        log = format_task_success_log("tj-cron", "compile", timestamp=ts)
        assert "[tj-cron]" in log
        assert "[INFO]" in log
        assert "compile" in log
        assert "2024-01-15" in log

    def test_failure_log(self):
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        log = format_task_failure_log(
            "tj-cron", "compile", exit_code=1, stderr="Error: syntax error", timestamp=ts
        )
        assert "[tj-cron]" in log
        assert "[ERROR]" in log
        assert "compile" in log
        assert "exit code 1" in log
        assert "syntax error" in log

    def test_failure_log_truncates_stderr(self):
        long_stderr = "x" * 2000
        log = format_task_failure_log(
            "tj-cron", "compile", exit_code=1, stderr=long_stderr
        )
        # The stderr in the log should be at most 1000 chars
        # Find the stderr portion after the newline
        parts = log.split("\n", 1)
        assert len(parts) == 2
        assert len(parts[1]) == MAX_STDERR_CHARS

    def test_timeout_log(self):
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        log = format_task_timeout_log("tj-cron", "compile", 300, timestamp=ts)
        assert "[tj-cron]" in log
        assert "[ERROR]" in log
        assert "compile" in log
        assert "300s" in log
        assert "timed out" in log

    def test_overlap_log(self):
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        log = format_task_overlap_log("tj-cron", "compile", 120.5, timestamp=ts)
        assert "[tj-cron]" in log
        assert "[WARNING]" in log
        assert "compile" in log
        assert "120.5s" in log
        assert "skipped" in log
