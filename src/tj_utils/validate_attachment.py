"""Email attachment validation for TaskJuggler timesheet submissions.

Validates incoming email attachments against the acceptance criteria:
- File must have a `.tji` extension
- Attachment size must not exceed 1 MB
- Total email message size must not exceed 5 MB
"""

from __future__ import annotations

from dataclasses import dataclass

# Maximum attachment size: 1 MB
MAX_ATTACHMENT_SIZE_BYTES = 1 * 1024 * 1024  # 1 MB

# Maximum total email message size: 5 MB
MAX_MESSAGE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB

# Required file extension for timesheet attachments
REQUIRED_EXTENSION = ".tji"


@dataclass
class AttachmentValidationResult:
    """Result of attachment validation.

    Attributes:
        valid: Whether the attachment passed all validation checks.
        reason: Human-readable reason for rejection (None if valid).
    """

    valid: bool
    reason: str | None = None


@dataclass
class MessageValidationResult:
    """Result of total message size validation.

    Attributes:
        valid: Whether the message size is within limits.
        reason: Human-readable reason for rejection (None if valid).
        message_size: The actual message size in bytes.
    """

    valid: bool
    reason: str | None = None
    message_size: int = 0


def validate_attachment(filename: str, size_bytes: int) -> AttachmentValidationResult:
    """Validate an email attachment for timesheet submission.

    Checks that the attachment has a `.tji` extension and does not
    exceed the 1 MB size limit.

    Args:
        filename: The filename of the attachment.
        size_bytes: The size of the attachment in bytes.

    Returns:
        AttachmentValidationResult indicating acceptance or rejection with reason.
    """
    if not filename.lower().endswith(REQUIRED_EXTENSION):
        return AttachmentValidationResult(
            valid=False,
            reason=f"Attachment '{filename}' does not have required .tji extension",
        )

    if size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
        size_mb = size_bytes / (1024 * 1024)
        return AttachmentValidationResult(
            valid=False,
            reason=(
                f"Attachment '{filename}' exceeds 1 MB size limit "
                f"(size: {size_mb:.2f} MB)"
            ),
        )

    return AttachmentValidationResult(valid=True)


def validate_message_size(message_size_bytes: int) -> MessageValidationResult:
    """Validate the total email message size.

    Rejects messages that exceed the 5 MB total size limit.

    Args:
        message_size_bytes: Total size of the email message in bytes.

    Returns:
        MessageValidationResult indicating acceptance or rejection with reason.
    """
    if message_size_bytes > MAX_MESSAGE_SIZE_BYTES:
        size_mb = message_size_bytes / (1024 * 1024)
        return MessageValidationResult(
            valid=False,
            reason=f"Message size {size_mb:.2f} MB exceeds 5 MB limit",
            message_size=message_size_bytes,
        )

    return MessageValidationResult(valid=True, message_size=message_size_bytes)


def format_rejection_log(
    sender: str,
    subject: str,
    reason: str,
) -> str:
    """Format a rejection log entry for an invalid email.

    Args:
        sender: Email address of the sender.
        subject: Subject line of the rejected email.
        reason: Reason for rejection.

    Returns:
        Formatted rejection log string containing sender, subject, and reason.
    """
    return f"Rejected email from {sender} (subject: '{subject}'): {reason}"


def format_size_rejection_log(
    sender: str,
    message_size_bytes: int,
) -> str:
    """Format a rejection log entry for an oversized email.

    Args:
        sender: Email address of the sender.
        message_size_bytes: Total size of the rejected message in bytes.

    Returns:
        Formatted rejection log string containing sender and message size.
    """
    size_mb = message_size_bytes / (1024 * 1024)
    return (
        f"Rejected email from {sender}: "
        f"message size {size_mb:.2f} MB exceeds 5 MB limit"
    )
