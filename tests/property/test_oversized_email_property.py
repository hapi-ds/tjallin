"""Property-based tests for oversized email rejection.

**Validates: Requirements 5.9**

Property 3: Oversized email rejection.
- Emails with total size > 5 MB are rejected.
- Emails with total size ≤ 5 MB are accepted.
- Rejection log contains sender address and message size.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_utils.validate_attachment import (
    MAX_MESSAGE_SIZE_BYTES,
    format_size_rejection_log,
    validate_message_size,
)

# --- Strategies ---

# Message sizes that exceed the 5 MB limit (> 5 MB up to 10 MB)
_oversized_message = st.integers(
    min_value=MAX_MESSAGE_SIZE_BYTES + 1,
    max_value=10 * 1024 * 1024,
)

# Message sizes within the 5 MB limit (1 MB to 5 MB inclusive)
_valid_message_size = st.integers(
    min_value=1 * 1024 * 1024,
    max_value=MAX_MESSAGE_SIZE_BYTES,
)

# Full range of message sizes for combined testing (1 MB to 10 MB)
_any_message_size = st.integers(
    min_value=1 * 1024 * 1024,
    max_value=10 * 1024 * 1024,
)

# Email addresses for rejection log tests
_email_address = st.from_regex(
    r"[a-z][a-z0-9]{0,10}@[a-z]{2,8}\.[a-z]{2,4}", fullmatch=True
)


class TestOversizedEmailRejectionProperty:
    """Property 3: Oversized email rejection.

    **Validates: Requirements 5.9**
    """

    @given(message_size_bytes=_oversized_message)
    @settings(max_examples=100)
    def test_messages_exceeding_5mb_are_rejected(
        self, message_size_bytes: int
    ) -> None:
        """Messages with total size > 5 MB are rejected."""
        result = validate_message_size(message_size_bytes)

        assert result.valid is False, (
            f"Expected valid=False for message size {message_size_bytes} bytes "
            f"({message_size_bytes / (1024 * 1024):.2f} MB), got valid=True"
        )
        assert result.reason is not None
        assert "5 mb" in result.reason.lower() or "size" in result.reason.lower(), (
            f"Rejection reason should mention size limit, got: '{result.reason}'"
        )
        assert result.message_size == message_size_bytes, (
            f"Expected message_size={message_size_bytes}, got {result.message_size}"
        )

    @given(message_size_bytes=_valid_message_size)
    @settings(max_examples=100)
    def test_messages_within_5mb_are_accepted(
        self, message_size_bytes: int
    ) -> None:
        """Messages with total size ≤ 5 MB are accepted."""
        result = validate_message_size(message_size_bytes)

        assert result.valid is True, (
            f"Expected valid=True for message size {message_size_bytes} bytes "
            f"({message_size_bytes / (1024 * 1024):.2f} MB), "
            f"got valid=False reason='{result.reason}'"
        )
        assert result.reason is None
        assert result.message_size == message_size_bytes, (
            f"Expected message_size={message_size_bytes}, got {result.message_size}"
        )

    @given(message_size_bytes=_any_message_size)
    @settings(max_examples=100)
    def test_rejection_iff_exceeds_5mb(
        self, message_size_bytes: int
    ) -> None:
        """Messages are rejected if and only if size > 5 MB."""
        result = validate_message_size(message_size_bytes)

        should_reject = message_size_bytes > MAX_MESSAGE_SIZE_BYTES

        assert result.valid is (not should_reject), (
            f"For size {message_size_bytes} bytes "
            f"({message_size_bytes / (1024 * 1024):.2f} MB), "
            f"expected valid={not should_reject}, got valid={result.valid}"
        )


class TestSizeRejectionLogProperty:
    """Rejection log for oversized emails contains sender address and message size.

    **Validates: Requirements 5.9**
    """

    @given(sender=_email_address, message_size_bytes=_oversized_message)
    @settings(max_examples=100)
    def test_rejection_log_contains_sender_and_size(
        self, sender: str, message_size_bytes: int
    ) -> None:
        """format_size_rejection_log output must contain sender and message size."""
        log_entry = format_size_rejection_log(sender, message_size_bytes)

        assert sender in log_entry, (
            f"Expected sender '{sender}' in log entry, got: '{log_entry}'"
        )
        # The log should contain the message size (formatted as MB)
        size_mb = message_size_bytes / (1024 * 1024)
        size_str = f"{size_mb:.2f}"
        assert size_str in log_entry, (
            f"Expected size '{size_str}' MB in log entry, got: '{log_entry}'"
        )
