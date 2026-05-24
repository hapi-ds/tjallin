"""Unit tests for the input handler module."""

from tj_chat.input_handler import (
    SlashCommandResult,
    handle_slash_command,
    is_empty_input,
    is_slash_command,
)


class TestIsEmptyInput:
    """Tests for is_empty_input()."""

    def test_empty_string(self) -> None:
        assert is_empty_input("") is True

    def test_whitespace_only(self) -> None:
        assert is_empty_input("   ") is True

    def test_tabs_and_newlines(self) -> None:
        assert is_empty_input("\t\n  \t") is True

    def test_non_empty(self) -> None:
        assert is_empty_input("hello") is False

    def test_whitespace_with_content(self) -> None:
        assert is_empty_input("  hello  ") is False


class TestIsSlashCommand:
    """Tests for is_slash_command()."""

    def test_slash_command(self) -> None:
        assert is_slash_command("/reset") is True

    def test_slash_with_spaces(self) -> None:
        assert is_slash_command("  /help") is True

    def test_not_slash_command(self) -> None:
        assert is_slash_command("hello") is False

    def test_slash_in_middle(self) -> None:
        assert is_slash_command("hello /reset") is False


class TestHandleSlashCommand:
    """Tests for handle_slash_command()."""

    def test_reset_command(self) -> None:
        result = handle_slash_command("/reset")
        assert result.is_valid is True
        assert result.action == "reset"
        assert "cleared" in result.response_text.lower() or "new session" in result.response_text.lower()

    def test_help_command(self) -> None:
        result = handle_slash_command("/help")
        assert result.is_valid is True
        assert result.action == "help"
        assert "/reset" in result.response_text
        assert "/help" in result.response_text

    def test_unknown_command(self) -> None:
        result = handle_slash_command("/foo")
        assert result.is_valid is False
        assert result.action == "unknown"
        assert "/foo" in result.response_text
        assert "/help" in result.response_text

    def test_case_insensitive(self) -> None:
        result = handle_slash_command("/RESET")
        assert result.is_valid is True
        assert result.action == "reset"

    def test_with_leading_whitespace(self) -> None:
        result = handle_slash_command("  /help  ")
        assert result.is_valid is True
        assert result.action == "help"
