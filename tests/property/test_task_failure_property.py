"""Property-based tests for task failure logging.

**Validates: Requirements 6.5**

Property 5: Task failure logging includes all required fields with stderr truncation.
- For any task name, exit code (1–255), and stderr string (0–5000 chars), the failure log
  SHALL contain an ISO 8601 timestamp, the task name, the exit code, and at most the first
  1000 characters of stderr output.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_utils.task_runner import MAX_STDERR_CHARS, format_task_failure_log, truncate_stderr

# Strategy for task names: realistic cron task names (alphanumeric + hyphens/underscores)
_task_name = st.text(
    alphabet=st.characters(categories=("L", "N"), include_characters="-_"),
    min_size=1,
    max_size=50,
)

# Strategy for exit codes: 1–255 (non-zero, indicating failure)
_exit_code = st.integers(min_value=1, max_value=255)

# Strategy for stderr strings: 0–5000 characters including special chars and unicode
_stderr = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "S", "Z"),
        exclude_characters="\x00",
    ),
    min_size=0,
    max_size=5000,
)

# Strategy for timestamps (aware datetimes in UTC)
_timestamp = st.datetimes(
    min_value=datetime(2000, 1, 1),
    max_value=datetime(2099, 12, 31),
    timezones=st.just(timezone.utc),
)


def _is_valid_iso8601(s: str) -> bool:
    """Check if a string is a valid ISO 8601 timestamp by parsing it."""
    try:
        datetime.fromisoformat(s)
        return True
    except (ValueError, TypeError):
        return False


class TestTaskFailureLoggingProperty:
    """Property 5: Task failure logging includes all required fields with stderr truncation.

    **Validates: Requirements 6.5**
    """

    @given(
        task_name=_task_name,
        exit_code=_exit_code,
        stderr=_stderr,
        ts=_timestamp,
    )
    @settings(max_examples=100)
    def test_failure_log_contains_iso8601_timestamp(
        self, task_name: str, exit_code: int, stderr: str, ts: datetime
    ) -> None:
        """The failure log contains a valid ISO 8601 timestamp."""
        result = format_task_failure_log(
            service_name="tj-cron",
            task_name=task_name,
            exit_code=exit_code,
            stderr=stderr,
            timestamp=ts,
        )

        # Extract the timestamp portion: second bracketed section
        # Format is: [SERVICE_NAME] [ISO8601_TIMESTAMP] [LEVEL] message
        parts = result.split("] [")
        assert len(parts) >= 3, (
            f"Expected at least 3 bracketed sections in log output, got: {result!r}"
        )

        timestamp_str = parts[1]
        assert _is_valid_iso8601(timestamp_str), (
            f"Expected valid ISO 8601 timestamp, got: {timestamp_str!r} in output: {result!r}"
        )

    @given(
        task_name=_task_name,
        exit_code=_exit_code,
        stderr=_stderr,
        ts=_timestamp,
    )
    @settings(max_examples=100)
    def test_failure_log_contains_task_name(
        self, task_name: str, exit_code: int, stderr: str, ts: datetime
    ) -> None:
        """The failure log contains the task name."""
        result = format_task_failure_log(
            service_name="tj-cron",
            task_name=task_name,
            exit_code=exit_code,
            stderr=stderr,
            timestamp=ts,
        )

        assert task_name in result, (
            f"Expected task name {task_name!r} in log output, got: {result!r}"
        )

    @given(
        task_name=_task_name,
        exit_code=_exit_code,
        stderr=_stderr,
        ts=_timestamp,
    )
    @settings(max_examples=100)
    def test_failure_log_contains_exit_code(
        self, task_name: str, exit_code: int, stderr: str, ts: datetime
    ) -> None:
        """The failure log contains the exit code."""
        result = format_task_failure_log(
            service_name="tj-cron",
            task_name=task_name,
            exit_code=exit_code,
            stderr=stderr,
            timestamp=ts,
        )

        assert f"exit code {exit_code}" in result, (
            f"Expected 'exit code {exit_code}' in log output, got: {result!r}"
        )

    @given(
        task_name=_task_name,
        exit_code=_exit_code,
        stderr=_stderr,
        ts=_timestamp,
    )
    @settings(max_examples=100)
    def test_failure_log_stderr_truncated_to_max_chars(
        self, task_name: str, exit_code: int, stderr: str, ts: datetime
    ) -> None:
        """The failure log contains at most the first 1000 chars of stderr."""
        result = format_task_failure_log(
            service_name="tj-cron",
            task_name=task_name,
            exit_code=exit_code,
            stderr=stderr,
            timestamp=ts,
        )

        if stderr:
            # The stderr portion appears after a newline in the log message
            # If stderr is non-empty, it should be included (truncated)
            expected_stderr = stderr[:MAX_STDERR_CHARS]
            assert expected_stderr in result, (
                f"Expected truncated stderr {expected_stderr!r} in log output, got: {result!r}"
            )

            # Verify no more than MAX_STDERR_CHARS of stderr appears
            # The full stderr (beyond 1000 chars) should NOT be in the output
            if len(stderr) > MAX_STDERR_CHARS:
                assert stderr not in result, (
                    f"Full stderr should be truncated but was found in output: {result!r}"
                )

    @given(
        task_name=_task_name,
        exit_code=_exit_code,
        stderr=_stderr,
        ts=_timestamp,
    )
    @settings(max_examples=100)
    def test_truncate_stderr_respects_max_chars(
        self, task_name: str, exit_code: int, stderr: str, ts: datetime
    ) -> None:
        """The truncate_stderr function returns at most max_chars characters."""
        truncated = truncate_stderr(stderr)

        assert len(truncated) <= MAX_STDERR_CHARS, (
            f"Expected at most {MAX_STDERR_CHARS} chars, got {len(truncated)}"
        )

        # If original is within limit, it should be unchanged
        if len(stderr) <= MAX_STDERR_CHARS:
            assert truncated == stderr, (
                f"Expected unchanged stderr for short input, got: {truncated!r}"
            )
        else:
            # If original exceeds limit, result should be the first MAX_STDERR_CHARS chars
            assert truncated == stderr[:MAX_STDERR_CHARS], (
                f"Expected first {MAX_STDERR_CHARS} chars of stderr"
            )
