"""Property-based tests for input validation and slash command handling.

**Validates: Requirements 11.7, 11.8**

Property 15: Whitespace-only input is rejected without agent invocation.
- For any string composed entirely of whitespace characters (spaces, tabs,
  newlines), the chat interface SHALL not send a message to the Chat Service.

Property 16: Unknown slash commands produce help suggestion.
- For any input string starting with / that does not match a known command
  (/reset, /help), the chat interface SHALL display an error message containing
  the unrecognized command text and a suggestion to use /help.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.input_handler import handle_slash_command, is_empty_input

# Strategy for whitespace-only strings (spaces, tabs, newlines, etc.)
_whitespace_chars = st.sampled_from(" \t\n\r\v\f")
_whitespace_only = st.text(alphabet=_whitespace_chars, min_size=1, max_size=50)

# Known commands that should NOT trigger the unknown-command path
_KNOWN_COMMANDS = frozenset({"/reset", "/help"})

# Strategy for unknown slash commands: starts with / followed by non-empty text
# that doesn't resolve to a known command after strip+lower
_command_char = st.characters(
    categories=("L", "N", "P"),
    exclude_characters="\x00\n\r",
)
_unknown_command_suffix = st.text(
    alphabet=_command_char, min_size=1, max_size=30
).filter(lambda s: f"/{s.strip().lower()}" not in _KNOWN_COMMANDS and s.strip() != "")


class TestWhitespaceInputRejected:
    """Property 15: Whitespace-only input is rejected without agent invocation.

    **Validates: Requirements 11.8**
    """

    @given(text=_whitespace_only)
    @settings(max_examples=200)
    def test_whitespace_only_is_detected_as_empty(self, text: str) -> None:
        """Any whitespace-only string is classified as empty input."""
        assert is_empty_input(text) is True

    @given(text=st.just(""))
    @settings(max_examples=5)
    def test_empty_string_is_detected_as_empty(self, text: str) -> None:
        """The empty string is classified as empty input."""
        assert is_empty_input(text) is True

    @given(
        leading=st.text(alphabet=_whitespace_chars, min_size=0, max_size=10),
        trailing=st.text(alphabet=_whitespace_chars, min_size=0, max_size=10),
        content=st.text(min_size=1, max_size=20).filter(lambda s: s.strip() != ""),
    )
    @settings(max_examples=100)
    def test_non_whitespace_content_is_not_empty(
        self, leading: str, trailing: str, content: str
    ) -> None:
        """Strings with any non-whitespace character are NOT classified as empty."""
        text = leading + content + trailing
        assert is_empty_input(text) is False


class TestUnknownSlashCommandsProduceHelpSuggestion:
    """Property 16: Unknown slash commands produce help suggestion.

    **Validates: Requirements 11.7**
    """

    @given(suffix=_unknown_command_suffix)
    @settings(max_examples=200)
    def test_unknown_command_returns_error_with_command_text(
        self, suffix: str
    ) -> None:
        """Unknown slash commands produce a result containing the command text."""
        command_input = f"/{suffix}"
        result = handle_slash_command(command_input)

        # The result must indicate the command is not valid
        assert result.is_valid is False
        assert result.action == "unknown"

        # The response must contain the unrecognized command text
        normalized_command = command_input.strip().lower()
        assert normalized_command in result.response_text

    @given(suffix=_unknown_command_suffix)
    @settings(max_examples=200)
    def test_unknown_command_suggests_help(self, suffix: str) -> None:
        """Unknown slash commands suggest using /help."""
        command_input = f"/{suffix}"
        result = handle_slash_command(command_input)

        # The response must contain a suggestion to use /help
        assert "/help" in result.response_text

    @given(
        command=st.sampled_from(["/reset", "/help"]),
        padding=st.text(alphabet=_whitespace_chars, min_size=0, max_size=5),
    )
    @settings(max_examples=50)
    def test_known_commands_are_valid(self, command: str, padding: str) -> None:
        """Known commands (/reset, /help) are always recognized as valid."""
        # Add optional leading/trailing whitespace
        text = padding + command + padding
        result = handle_slash_command(text)

        assert result.is_valid is True
        assert result.action in ("reset", "help")
