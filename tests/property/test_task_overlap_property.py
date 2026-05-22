"""Property-based tests for overlapping task prevention.

**Validates: Requirements 6.7**

Property 6: Overlapping task execution is prevented.
- For any task name and elapsed time, the overlap warning log SHALL contain
  the task name and elapsed time, indicating the task was skipped because
  a previous execution is still running.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_utils.task_runner import format_task_overlap_log

# Strategy for task names: realistic cron task names (alphanumeric + hyphens/underscores)
_task_name = st.text(
    alphabet=st.characters(categories=("L", "N"), include_characters="-_"),
    min_size=1,
    max_size=50,
)

# Strategy for elapsed times: positive floats representing seconds since previous execution started
_elapsed_seconds = st.floats(
    min_value=0.1,
    max_value=86400.0,  # Up to 24 hours
    allow_nan=False,
    allow_infinity=False,
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


class TestTaskOverlapPreventionProperty:
    """Property 6: Overlapping task execution is prevented.

    **Validates: Requirements 6.7**
    """

    @given(
        task_name=_task_name,
        elapsed=_elapsed_seconds,
        ts=_timestamp,
    )
    @settings(max_examples=100)
    def test_overlap_log_contains_task_name(
        self, task_name: str, elapsed: float, ts: datetime
    ) -> None:
        """The overlap warning log contains the task name."""
        result = format_task_overlap_log(
            service_name="tj-cron",
            task_name=task_name,
            elapsed_seconds=elapsed,
            timestamp=ts,
        )

        assert task_name in result, (
            f"Expected task name {task_name!r} in overlap log, got: {result!r}"
        )

    @given(
        task_name=_task_name,
        elapsed=_elapsed_seconds,
        ts=_timestamp,
    )
    @settings(max_examples=100)
    def test_overlap_log_contains_elapsed_time(
        self, task_name: str, elapsed: float, ts: datetime
    ) -> None:
        """The overlap warning log contains the elapsed time."""
        result = format_task_overlap_log(
            service_name="tj-cron",
            task_name=task_name,
            elapsed_seconds=elapsed,
            timestamp=ts,
        )

        # The elapsed time is formatted as "{elapsed:.1f}s"
        expected_elapsed = f"{elapsed:.1f}s"
        assert expected_elapsed in result, (
            f"Expected elapsed time {expected_elapsed!r} in overlap log, got: {result!r}"
        )

    @given(
        task_name=_task_name,
        elapsed=_elapsed_seconds,
        ts=_timestamp,
    )
    @settings(max_examples=100)
    def test_overlap_log_is_warning_level(
        self, task_name: str, elapsed: float, ts: datetime
    ) -> None:
        """The overlap log uses WARNING level."""
        result = format_task_overlap_log(
            service_name="tj-cron",
            task_name=task_name,
            elapsed_seconds=elapsed,
            timestamp=ts,
        )

        assert "[WARNING]" in result, (
            f"Expected [WARNING] level in overlap log, got: {result!r}"
        )

    @given(
        task_name=_task_name,
        elapsed=_elapsed_seconds,
        ts=_timestamp,
    )
    @settings(max_examples=100)
    def test_overlap_log_contains_iso8601_timestamp(
        self, task_name: str, elapsed: float, ts: datetime
    ) -> None:
        """The overlap warning log contains a valid ISO 8601 timestamp."""
        result = format_task_overlap_log(
            service_name="tj-cron",
            task_name=task_name,
            elapsed_seconds=elapsed,
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
        elapsed=_elapsed_seconds,
        ts=_timestamp,
    )
    @settings(max_examples=100)
    def test_overlap_log_indicates_skip_behavior(
        self, task_name: str, elapsed: float, ts: datetime
    ) -> None:
        """The overlap warning log indicates the task was skipped."""
        result = format_task_overlap_log(
            service_name="tj-cron",
            task_name=task_name,
            elapsed_seconds=elapsed,
            timestamp=ts,
        )

        assert "skipped" in result.lower(), (
            f"Expected 'skipped' indication in overlap log, got: {result!r}"
        )
