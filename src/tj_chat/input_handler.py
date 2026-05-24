"""Input validation and slash command handling for the chat interface.

Provides functions to validate user input and process slash commands
like /reset and /help.
"""

from __future__ import annotations

from pydantic import BaseModel


class SlashCommandResult(BaseModel):
    """Result of processing a slash command.

    Attributes:
        command: The command that was entered (e.g., "/reset").
        is_valid: Whether it's a recognized command.
        action: The action type: "reset", "help", or "unknown".
        response_text: The text to display to the user.
    """

    command: str
    is_valid: bool
    action: str  # "reset", "help", "unknown"
    response_text: str


_HELP_TEXT = """Available commands:
• /reset — Clear conversation history and start a new session
• /help — Display this help message

Capabilities:
• Review project plan (tasks, resources, timelines)
• Update tasks and resources
• Write timesheet/booking entries
• Create journal entries
• Generate reports (Gantt charts, resource reports, etc.)
• Search TaskJuggler documentation
"""

_KNOWN_COMMANDS = frozenset({"/reset", "/help"})


def is_empty_input(text: str) -> bool:
    """Check if input is empty or whitespace-only.

    Args:
        text: The user's input text.

    Returns:
        True if the text is empty or contains only whitespace.
    """
    return not text or not text.strip()


def is_slash_command(text: str) -> bool:
    """Check if input starts with a slash (is a command).

    Args:
        text: The user's input text.

    Returns:
        True if the text starts with '/'.
    """
    return text.strip().startswith("/")


def handle_slash_command(text: str) -> SlashCommandResult:
    """Process a slash command and return the result.

    Recognized commands:
    - /reset: Clear conversation and start new session
    - /help: Display available commands and capabilities

    Unknown commands return an error with a suggestion to use /help.

    Args:
        text: The user's input text (must start with '/').

    Returns:
        SlashCommandResult with the command, validity, action, and response text.
    """
    command = text.strip().lower()

    if command == "/reset":
        return SlashCommandResult(
            command=command,
            is_valid=True,
            action="reset",
            response_text="Conversation cleared. Starting a new session.",
        )

    if command == "/help":
        return SlashCommandResult(
            command=command,
            is_valid=True,
            action="help",
            response_text=_HELP_TEXT,
        )

    # Unknown command
    return SlashCommandResult(
        command=command,
        is_valid=False,
        action="unknown",
        response_text=f"Unknown command: {command}. Type /help to see available commands.",
    )
