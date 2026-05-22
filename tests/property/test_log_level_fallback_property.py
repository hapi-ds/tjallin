"""Property-based tests for invalid log level fallback behavior.

**Validates: Requirements 8.4**

Property 7: Invalid log level falls back to INFO with warning.
- When the log level value is not in {DEBUG, INFO, WARNING, ERROR},
  validate_log_level returns ("INFO", warning_message) where warning_message
  contains the invalid value.
- When the log level value IS in {DEBUG, INFO, WARNING, ERROR},
  validate_log_level returns (value.upper(), None).
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_utils.validate_env import VALID_LOG_LEVELS, validate_log_level

# Strategy for strings that are NOT valid log levels (case-insensitive)
_invalid_log_level = st.text(min_size=1).filter(
    lambda s: s.strip().upper() not in VALID_LOG_LEVELS and s.strip() != ""
)

# Strategy for valid log levels in any case variation
_valid_log_level = st.sampled_from(sorted(VALID_LOG_LEVELS)).flatmap(
    lambda level: st.sampled_from(
        [level, level.lower(), level.capitalize(), level.swapcase()]
    )
)


class TestInvalidLogLevelFallback:
    """Property 7: Invalid log level falls back to INFO with warning.

    **Validates: Requirements 8.4**
    """

    @given(value=_invalid_log_level)
    @settings(max_examples=100)
    def test_invalid_log_level_returns_info_with_warning(self, value: str) -> None:
        """When value is not a valid log level, effective level is INFO and warning contains the invalid value."""
        effective_level, warning = validate_log_level(value)

        # Effective level must fall back to INFO
        assert effective_level == "INFO", (
            f"Expected effective level 'INFO' for invalid input {value!r}, "
            f"got {effective_level!r}"
        )

        # Warning must not be None
        assert warning is not None, (
            f"Expected a warning message for invalid input {value!r}, got None"
        )

        # Warning must contain the invalid value
        assert value in warning, (
            f"Expected warning to contain the invalid value {value!r}, "
            f"got warning: {warning!r}"
        )

    @given(value=_valid_log_level)
    @settings(max_examples=100)
    def test_valid_log_level_returns_level_without_warning(self, value: str) -> None:
        """When value IS a valid log level, returns (value.upper(), None)."""
        effective_level, warning = validate_log_level(value)

        # Effective level must be the uppercased value
        assert effective_level == value.strip().upper(), (
            f"Expected effective level {value.strip().upper()!r} for valid input {value!r}, "
            f"got {effective_level!r}"
        )

        # No warning for valid levels
        assert warning is None, (
            f"Expected no warning for valid input {value!r}, got: {warning!r}"
        )
