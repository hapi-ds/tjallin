"""Property-based tests for log line formatting.

**Validates: Requirements 8.2**

Property 4: Log entry format includes service name and ISO 8601 timestamp.
- For any service name and log message, the log formatting function SHALL produce output
  containing the service name and a valid ISO 8601 timestamp, regardless of message content
  or length.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_utils.format_log import format_log

# Strategy for service names: realistic Docker service names (alphanumeric + hyphens)
_service_name = st.text(
    alphabet=st.characters(categories=("L", "N"), include_characters="-_"),
    min_size=1,
    max_size=50,
)

# Strategy for log levels
_log_level = st.sampled_from(["DEBUG", "INFO", "WARNING", "ERROR"])

# Strategy for message strings including special chars and unicode
_message = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "S", "Z"),
        exclude_characters="\x00",
    ),
    min_size=0,
    max_size=500,
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


class TestLogFormatContainsServiceNameAndTimestamp:
    """Property 4: Log entry format includes service name and ISO 8601 timestamp.

    **Validates: Requirements 8.2**
    """

    @given(service_name=_service_name, level=_log_level, message=_message, ts=_timestamp)
    @settings(max_examples=100)
    def test_output_contains_service_name(
        self, service_name: str, level: str, message: str, ts: datetime
    ) -> None:
        """The formatted log line contains the service name in brackets."""
        result = format_log(service_name, level, message, timestamp=ts)

        assert f"[{service_name}]" in result, (
            f"Expected '[{service_name}]' in log output, got: {result!r}"
        )

    @given(service_name=_service_name, level=_log_level, message=_message, ts=_timestamp)
    @settings(max_examples=100)
    def test_output_contains_valid_iso8601_timestamp(
        self, service_name: str, level: str, message: str, ts: datetime
    ) -> None:
        """The formatted log line contains a valid ISO 8601 timestamp in brackets."""
        result = format_log(service_name, level, message, timestamp=ts)

        # Extract the timestamp portion: second bracketed section
        # Format is: [SERVICE_NAME] [ISO8601_TIMESTAMP] [LEVEL] message
        parts = result.split("] [")
        assert len(parts) >= 3, (
            f"Expected at least 3 bracketed sections in log output, got: {result!r}"
        )

        # The timestamp is the second bracketed section
        # parts[0] = "[SERVICE_NAME", parts[1] = "ISO8601_TIMESTAMP", parts[2] = "LEVEL] message"
        timestamp_str = parts[1]
        assert _is_valid_iso8601(timestamp_str), (
            f"Expected valid ISO 8601 timestamp, got: {timestamp_str!r} in output: {result!r}"
        )

    @given(service_name=_service_name, level=_log_level, message=_message, ts=_timestamp)
    @settings(max_examples=100)
    def test_output_contains_message(
        self, service_name: str, level: str, message: str, ts: datetime
    ) -> None:
        """The formatted log line contains the original message."""
        result = format_log(service_name, level, message, timestamp=ts)

        assert message in result, (
            f"Expected message {message!r} in log output, got: {result!r}"
        )

    @given(service_name=_service_name, level=_log_level, message=_message, ts=_timestamp)
    @settings(max_examples=100)
    def test_output_matches_expected_format(
        self, service_name: str, level: str, message: str, ts: datetime
    ) -> None:
        """The formatted log line matches the exact format: [SERVICE] [TIMESTAMP] [LEVEL] message."""
        result = format_log(service_name, level, message, timestamp=ts)

        expected_timestamp = ts.isoformat()
        expected = f"[{service_name}] [{expected_timestamp}] [{level}] {message}"
        assert result == expected, (
            f"Expected exact format:\n  {expected!r}\nGot:\n  {result!r}"
        )
