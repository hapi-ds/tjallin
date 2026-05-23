"""Mail user parsing and validation for TJ_MAIL_USERS environment variable.

Parses comma-separated user:password pairs into validated MailUser objects.
Supports 1–50 entries with username and password format validation.
Falls back to TJ_MAIL_SENDER local-part when TJ_MAIL_USERS is unset or empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Maximum number of user entries allowed
MAX_ENTRIES = 50

# Username constraints
MAX_USERNAME_LENGTH = 64
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9._-]+$")

# Password constraints
MAX_PASSWORD_LENGTH = 128


@dataclass
class MailUser:
    """A validated mail user account.

    Attributes:
        username: The mail username (1–64 chars, alphanumeric plus `-_.`).
        password: The mail password (1–128 chars, no commas or colons).
    """

    username: str
    password: str


@dataclass
class ParseResult:
    """Result of parsing TJ_MAIL_USERS.

    Attributes:
        users: List of successfully validated MailUser objects.
        errors: List of error messages for malformed or invalid entries.
    """

    users: list[MailUser] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_mail_users(
    value: str | None, mail_sender: str = "taskjuggler@taskjuggler.local"
) -> ParseResult:
    """Parse TJ_MAIL_USERS into validated user accounts.

    Args:
        value: The TJ_MAIL_USERS environment variable value, or None/empty.
        mail_sender: The TJ_MAIL_SENDER value for default account fallback.

    Returns:
        ParseResult with valid users and any error messages for malformed entries.
    """
    result = ParseResult()

    if not value or not value.strip():
        local_part = _extract_local_part(mail_sender)
        result.users.append(MailUser(username=local_part, password=local_part))
        return result

    entries = value.split(",")

    for i, entry in enumerate(entries):
        if i >= MAX_ENTRIES:
            result.errors.append(
                f"Entry {i + 1}: exceeds maximum of {MAX_ENTRIES} entries"
            )
            continue

        entry = entry.strip()

        if not entry:
            result.errors.append(f"Entry {i + 1}: empty entry")
            continue

        if ":" not in entry:
            result.errors.append(f"Entry {i + 1}: missing ':' separator in '{entry}'")
            continue

        # Split on first colon only to allow colons in... wait, no.
        # Password cannot contain colons per validation rules.
        # But we split on first colon to get the raw parts, then validate.
        parts = entry.split(":", 1)
        username = parts[0]
        password = parts[1]

        username_error = _validate_username(username)
        if username_error:
            result.errors.append(f"Entry {i + 1}: {username_error}")
            continue

        password_error = _validate_password(password)
        if password_error:
            result.errors.append(f"Entry {i + 1}: {password_error}")
            continue

        result.users.append(MailUser(username=username, password=password))

    return result


def _validate_username(username: str) -> str | None:
    """Validate a username against format rules.

    Args:
        username: The username to validate.

    Returns:
        Error message string if invalid, None if valid.
    """
    if not username:
        return "username is empty"

    if len(username) > MAX_USERNAME_LENGTH:
        return f"username '{username[:20]}...' exceeds {MAX_USERNAME_LENGTH} characters"

    if not USERNAME_PATTERN.match(username):
        return (
            f"username '{username}' contains invalid characters"
            " (allowed: a-z, A-Z, 0-9, -, _, .)"
        )

    return None


def _validate_password(password: str) -> str | None:
    """Validate a password against format rules.

    Args:
        password: The password to validate.

    Returns:
        Error message string if invalid, None if valid.
    """
    if not password:
        return "password is empty"

    if len(password) > MAX_PASSWORD_LENGTH:
        return f"password exceeds {MAX_PASSWORD_LENGTH} characters"

    if "," in password:
        return "password contains comma"

    if ":" in password:
        return "password contains colon"

    return None


def _extract_local_part(mail_sender: str) -> str:
    """Extract the local-part (before @) from an email address.

    Args:
        mail_sender: An email address string.

    Returns:
        The local-part of the email address, or the full string if no @ is present.
    """
    if "@" in mail_sender:
        return mail_sender.split("@", 1)[0]
    return mail_sender
