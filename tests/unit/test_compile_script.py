"""Unit tests for compilation script log format patterns.

Since the compilation script (services/tj-core/scripts/compile.sh) runs inside
a Docker container with tj3, we validate the log format patterns it should produce
by testing against the shared format_log utility.

Validates: Requirements 3.4, 3.5, 3.6
"""

import re
from datetime import datetime, timezone

from tj_utils.format_log import format_log


# Regex patterns matching the expected log output from compile.sh
SUCCESS_PATTERN = re.compile(
    r"^\[tj-core\] \[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\]]*\] \[INFO\] "
    r"Project compilation completed: \d+ reports generated$"
)

ERROR_PATTERN = re.compile(
    r"^\[tj-core\] \[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[^\]]*\] \[ERROR\] "
    r"Project compilation failed with exit code \d+$"
)


class TestCompilationSuccessLogFormat:
    """Test that success log lines match the expected format from compile.sh."""

    def test_success_log_matches_pattern(self):
        """Success log must match: [tj-core] [ISO8601] [INFO] Project compilation completed: N reports generated."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_log(
            "tj-core", "INFO", "Project compilation completed: 5 reports generated", timestamp=ts
        )
        assert SUCCESS_PATTERN.match(result), f"Log line did not match expected pattern: {result}"

    def test_success_log_contains_report_count(self):
        """Success log includes the number of reports generated."""
        ts = datetime(2024, 6, 1, 8, 0, 0, tzinfo=timezone.utc)
        result = format_log(
            "tj-core", "INFO", "Project compilation completed: 12 reports generated", timestamp=ts
        )
        assert "12 reports generated" in result

    def test_success_log_zero_reports(self):
        """Success log works with zero reports."""
        ts = datetime(2024, 3, 10, 14, 45, 0, tzinfo=timezone.utc)
        result = format_log(
            "tj-core", "INFO", "Project compilation completed: 0 reports generated", timestamp=ts
        )
        assert SUCCESS_PATTERN.match(result)

    def test_success_log_contains_iso8601_timestamp(self):
        """Success log contains a valid ISO 8601 timestamp."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_log(
            "tj-core", "INFO", "Project compilation completed: 3 reports generated", timestamp=ts
        )
        assert "2024-01-15T10:30:00" in result

    def test_success_log_uses_info_level(self):
        """Success log uses INFO level."""
        result = format_log(
            "tj-core", "INFO", "Project compilation completed: 1 reports generated"
        )
        assert "[INFO]" in result


class TestCompilationFailureLogFormat:
    """Test that failure log lines match the expected format from compile.sh."""

    def test_failure_log_matches_pattern(self):
        """Failure log must match: [tj-core] [ISO8601] [ERROR] Project compilation failed with exit code N."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_log(
            "tj-core", "ERROR", "Project compilation failed with exit code 1", timestamp=ts
        )
        assert ERROR_PATTERN.match(result), f"Log line did not match expected pattern: {result}"

    def test_failure_log_contains_exit_code(self):
        """Failure log includes the exit code from tj3."""
        ts = datetime(2024, 2, 20, 16, 0, 0, tzinfo=timezone.utc)
        result = format_log(
            "tj-core", "ERROR", "Project compilation failed with exit code 127", timestamp=ts
        )
        assert "exit code 127" in result

    def test_failure_log_uses_error_level(self):
        """Failure log uses ERROR level."""
        result = format_log(
            "tj-core", "ERROR", "Project compilation failed with exit code 2"
        )
        assert "[ERROR]" in result

    def test_failure_log_contains_iso8601_timestamp(self):
        """Failure log contains a valid ISO 8601 timestamp."""
        ts = datetime(2024, 7, 4, 23, 59, 59, tzinfo=timezone.utc)
        result = format_log(
            "tj-core", "ERROR", "Project compilation failed with exit code 1", timestamp=ts
        )
        assert "2024-07-04T23:59:59" in result

    def test_failure_log_preserves_full_error_context(self):
        """The error log format preserves the exit code for debugging."""
        for code in [1, 2, 126, 127, 255]:
            result = format_log(
                "tj-core", "ERROR", f"Project compilation failed with exit code {code}"
            )
            assert f"exit code {code}" in result


class TestFormatLogForCompilation:
    """Test that format_log produces the expected format for compilation messages."""

    def test_format_log_service_name_bracketed(self):
        """format_log wraps service name in brackets."""
        result = format_log("tj-core", "INFO", "test")
        assert result.startswith("[tj-core]")

    def test_format_log_level_bracketed(self):
        """format_log wraps level in brackets."""
        ts = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        result = format_log("tj-core", "INFO", "msg", timestamp=ts)
        assert "[INFO]" in result

    def test_format_log_timestamp_bracketed(self):
        """format_log wraps ISO 8601 timestamp in brackets."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_log("tj-core", "INFO", "msg", timestamp=ts)
        assert "[2024-01-15T10:30:00+00:00]" in result

    def test_format_log_message_not_bracketed(self):
        """format_log does not wrap the message in brackets."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_log("tj-core", "INFO", "hello world", timestamp=ts)
        # Message should appear after the last bracket group, not wrapped
        parts = result.split("] ")
        assert parts[-1] == "hello world"

    def test_format_log_compilation_success_message(self):
        """format_log produces correct output for a compilation success message."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_log(
            "tj-core", "INFO", "Project compilation completed: 5 reports generated", timestamp=ts
        )
        expected = "[tj-core] [2024-01-15T10:30:00+00:00] [INFO] Project compilation completed: 5 reports generated"
        assert result == expected

    def test_format_log_compilation_failure_message(self):
        """format_log produces correct output for a compilation failure message."""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = format_log(
            "tj-core", "ERROR", "Project compilation failed with exit code 1", timestamp=ts
        )
        expected = "[tj-core] [2024-01-15T10:30:00+00:00] [ERROR] Project compilation failed with exit code 1"
        assert result == expected
