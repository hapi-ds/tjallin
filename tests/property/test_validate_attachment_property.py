"""Property-based tests for email attachment validation.

**Validates: Requirements 5.7, 5.8**

Property 2: Email attachment validation accepts only .tji files within size limit.
- An attachment is valid iff its filename ends with `.tji` (case-insensitive) AND size ≤ 1 MB.
- Rejection log entries must contain the sender address, subject line, and reason.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_utils.validate_attachment import (
    MAX_ATTACHMENT_SIZE_BYTES,
    REQUIRED_EXTENSION,
    format_rejection_log,
    validate_attachment,
)

# --- Strategies ---

# Filenames that end with .tji (valid extension)
_tji_basename = st.text(
    alphabet=st.characters(categories=("L", "N", "P"), exclude_characters=".\x00/\\"),
    min_size=1,
    max_size=30,
)
_valid_filename = _tji_basename.map(lambda base: base + REQUIRED_EXTENSION)

# Filenames that do NOT end with .tji
_non_tji_extensions = st.sampled_from([".txt", ".csv", ".pdf", ".tjp", ".doc", ".tji.bak", ""])
_invalid_filename = _tji_basename.map(lambda base: base).flatmap(
    lambda base: _non_tji_extensions.map(lambda ext: base + ext)
).filter(lambda f: not f.lower().endswith(REQUIRED_EXTENSION))

# Sizes within the 1 MB limit (0 to MAX_ATTACHMENT_SIZE_BYTES inclusive)
_valid_size = st.integers(min_value=0, max_value=MAX_ATTACHMENT_SIZE_BYTES)

# Sizes exceeding the 1 MB limit (up to 2 MB)
_oversized = st.integers(min_value=MAX_ATTACHMENT_SIZE_BYTES + 1, max_value=2 * 1024 * 1024)

# Full range of sizes for combined testing (0 to 2 MB)
_any_size = st.integers(min_value=0, max_value=2 * 1024 * 1024)

# Email metadata for rejection log tests
_email_address = st.from_regex(r"[a-z][a-z0-9]{0,10}@[a-z]{2,8}\.[a-z]{2,4}", fullmatch=True)
_subject_line = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S", "Z"), exclude_characters="\x00"),
    min_size=1,
    max_size=80,
)
_reason_text = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "S", "Z"), exclude_characters="\x00"),
    min_size=1,
    max_size=120,
)


class TestAttachmentValidationProperty:
    """Property 2: Email attachment validation accepts only .tji files within size limit.

    **Validates: Requirements 5.7, 5.8**
    """

    @given(filename=_valid_filename, size_bytes=_valid_size)
    @settings(max_examples=100)
    def test_valid_tji_within_size_limit_is_accepted(
        self, filename: str, size_bytes: int
    ) -> None:
        """Attachments with .tji extension AND size ≤ 1 MB are accepted."""
        result = validate_attachment(filename, size_bytes)

        assert result.valid is True, (
            f"Expected valid=True for filename='{filename}' size={size_bytes}, "
            f"got valid=False reason='{result.reason}'"
        )
        assert result.reason is None

    @given(filename=_invalid_filename, size_bytes=_any_size)
    @settings(max_examples=100)
    def test_non_tji_extension_is_rejected(
        self, filename: str, size_bytes: int
    ) -> None:
        """Attachments without .tji extension are rejected regardless of size."""
        result = validate_attachment(filename, size_bytes)

        assert result.valid is False, (
            f"Expected valid=False for non-.tji filename='{filename}', got valid=True"
        )
        assert result.reason is not None
        assert ".tji" in result.reason.lower() or "extension" in result.reason.lower(), (
            f"Rejection reason should mention .tji or extension, got: '{result.reason}'"
        )

    @given(filename=_valid_filename, size_bytes=_oversized)
    @settings(max_examples=100)
    def test_oversized_tji_is_rejected(
        self, filename: str, size_bytes: int
    ) -> None:
        """Attachments with .tji extension but size > 1 MB are rejected."""
        result = validate_attachment(filename, size_bytes)

        assert result.valid is False, (
            f"Expected valid=False for oversized attachment "
            f"filename='{filename}' size={size_bytes}, got valid=True"
        )
        assert result.reason is not None
        assert "size" in result.reason.lower() or "1 mb" in result.reason.lower(), (
            f"Rejection reason should mention size limit, got: '{result.reason}'"
        )

    @given(filename=_invalid_filename, size_bytes=_oversized)
    @settings(max_examples=100)
    def test_invalid_extension_and_oversized_is_rejected(
        self, filename: str, size_bytes: int
    ) -> None:
        """Attachments failing both checks (wrong extension AND oversized) are rejected."""
        result = validate_attachment(filename, size_bytes)

        assert result.valid is False, (
            f"Expected valid=False for filename='{filename}' size={size_bytes}, got valid=True"
        )
        assert result.reason is not None


class TestRejectionLogProperty:
    """Rejection log format contains sender address, subject line, and reason.

    **Validates: Requirements 5.7, 5.8**
    """

    @given(sender=_email_address, subject=_subject_line, reason=_reason_text)
    @settings(max_examples=100)
    def test_rejection_log_contains_sender_subject_reason(
        self, sender: str, subject: str, reason: str
    ) -> None:
        """format_rejection_log output must contain the sender, subject, and reason."""
        log_entry = format_rejection_log(sender, subject, reason)

        assert sender in log_entry, (
            f"Expected sender '{sender}' in log entry, got: '{log_entry}'"
        )
        assert subject in log_entry, (
            f"Expected subject '{subject}' in log entry, got: '{log_entry}'"
        )
        assert reason in log_entry, (
            f"Expected reason '{reason}' in log entry, got: '{log_entry}'"
        )
