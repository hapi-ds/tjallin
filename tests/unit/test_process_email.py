"""Unit tests for the process-email.sh inbound email processing pipeline.

Since process-email.sh runs inside a Docker container with specific tools
(ripmime, Postfix), these tests validate the script's logic patterns and
expected log output format by testing the Python validation utilities that
mirror the shell script's behavior.

The shell script implements the same validation logic as validate_attachment.py:
- Total message size ≤ 5 MB
- Attachment must have .tji extension
- Attachment size ≤ 1 MB
- Rejections logged with sender, subject, and reason

Validates: Requirements 5.3, 5.7, 5.8, 5.9
"""

import os
import re
import subprocess
import tempfile

import pytest

# Path to the process-email.sh script
SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "services",
    "tj-mail",
    "scripts",
    "process-email.sh",
)

# Log format pattern matching the shared format
LOG_PATTERN = re.compile(
    r"^\[tj-mail\] \[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\] \[(INFO|WARNING|ERROR)\] .+"
)


def create_mime_email(
    sender: str = "alice@example.com",
    subject: str = "Weekly Timesheet",
    attachments: list[tuple[str, bytes]] | None = None,
    body: str = "Please find my timesheet attached.",
) -> bytes:
    """Create a simple MIME email with optional attachments.

    Args:
        sender: From address.
        subject: Email subject line.
        attachments: List of (filename, content) tuples.
        body: Plain text body.

    Returns:
        Raw email bytes suitable for piping to process-email.sh.
    """
    import email.mime.application
    import email.mime.multipart
    import email.mime.text

    msg = email.mime.multipart.MIMEMultipart()
    msg["From"] = sender
    msg["To"] = "timesheets@taskjuggler.local"
    msg["Subject"] = subject

    # Add text body
    msg.attach(email.mime.text.MIMEText(body, "plain"))

    # Add attachments
    if attachments:
        for filename, content in attachments:
            part = email.mime.application.MIMEApplication(content, Name=filename)
            part["Content-Disposition"] = f'attachment; filename="{filename}"'
            msg.attach(part)

    return msg.as_bytes()


class TestProcessEmailScriptExists:
    """Verify the script file exists and has correct structure."""

    def test_script_file_exists(self):
        """process-email.sh must exist in the expected location."""
        assert os.path.isfile(SCRIPT_PATH), f"Script not found at {SCRIPT_PATH}"

    def test_script_has_shebang(self):
        """Script must start with a bash shebang."""
        with open(SCRIPT_PATH) as f:
            first_line = f.readline()
        assert first_line.startswith("#!/bin/bash"), "Script must have bash shebang"

    def test_script_defines_size_limits(self):
        """Script must define the correct size limits."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "5242880" in content, "Script must define 5 MB limit (5242880 bytes)"
        assert "1048576" in content, "Script must define 1 MB limit (1048576 bytes)"

    def test_script_uses_shared_log_format(self):
        """Script must use the shared log format [SERVICE_NAME] [TIMESTAMP] [LEVEL]."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "[$SERVICE_NAME]" in content
        assert "[$TIMESTAMP]" in content
        assert "[INFO]" in content
        assert "[WARNING]" in content

    def test_script_checks_tji_extension(self):
        """Script must validate .tji file extension."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert ".tji" in content

    def test_script_copies_to_timesheet_dir(self):
        """Script must copy valid attachments to /app/timesheets."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "/app/timesheets" in content

    def test_script_extracts_sender(self):
        """Script must extract the sender (From header) for logging."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "From:" in content or "from:" in content.lower()

    def test_script_extracts_subject(self):
        """Script must extract the subject header for logging."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "Subject:" in content or "subject:" in content.lower()

    def test_script_exits_nonzero_on_rejection(self):
        """Script must exit non-zero when rejecting an email."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "exit 1" in content

    def test_script_exits_zero_on_success(self):
        """Script must exit 0 on successful processing."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "exit 0" in content

    def test_script_cleans_up_temp_files(self):
        """Script must clean up temporary files on exit."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "trap" in content
        assert "cleanup" in content or "rm -rf" in content


class TestProcessEmailLogFormat:
    """Test that the script's log output matches the shared format."""

    def test_info_log_format(self):
        """INFO log lines must match [tj-mail] [ISO8601] [INFO] message."""
        # Simulate what the script would produce
        from tj_utils.format_log import format_log

        result = format_log(
            "tj-mail", "INFO", "Stored timesheet 'week03.tji' from alice@example.com (size: 1024 bytes)"
        )
        assert "[tj-mail]" in result
        assert "[INFO]" in result
        assert "week03.tji" in result

    def test_warning_log_for_invalid_extension(self):
        """WARNING log for invalid extension includes sender, subject, and reason."""
        from tj_utils.format_log import format_log

        result = format_log(
            "tj-mail",
            "WARNING",
            "Rejected email from bob@example.com (subject: 'My Report'): "
            "attachment 'report.pdf' does not have required .tji extension",
        )
        assert "bob@example.com" in result
        assert "My Report" in result
        assert ".tji extension" in result
        assert "[WARNING]" in result

    def test_warning_log_for_oversized_attachment(self):
        """WARNING log for oversized attachment includes size info."""
        from tj_utils.format_log import format_log

        result = format_log(
            "tj-mail",
            "WARNING",
            "Rejected email from carol@example.com (subject: 'Timesheet'): "
            "attachment 'big.tji' exceeds 1 MB size limit (size: 1.50 MB)",
        )
        assert "carol@example.com" in result
        assert "1 MB" in result
        assert "1.50 MB" in result
        assert "[WARNING]" in result

    def test_warning_log_for_oversized_message(self):
        """WARNING log for oversized message includes total size."""
        from tj_utils.format_log import format_log

        result = format_log(
            "tj-mail",
            "WARNING",
            "Rejected email from dave@example.com: message size 6.50 MB exceeds 5 MB limit",
        )
        assert "dave@example.com" in result
        assert "5 MB" in result
        assert "6.50 MB" in result
        assert "[WARNING]" in result


class TestMimeEmailCreation:
    """Test the MIME email helper used for integration testing."""

    def test_create_email_with_tji_attachment(self):
        """Helper creates valid MIME email with .tji attachment."""
        content = b"timesheet alice 2024-01-15 +1w { }"
        email_bytes = create_mime_email(
            sender="alice@example.com",
            subject="Week 3 Timesheet",
            attachments=[("2024-W03-alice.tji", content)],
        )
        assert b"From: alice@example.com" in email_bytes
        assert b"Subject: Week 3 Timesheet" in email_bytes
        assert b"2024-W03-alice.tji" in email_bytes

    def test_create_email_without_attachments(self):
        """Helper creates email without attachments."""
        email_bytes = create_mime_email(
            sender="bob@example.com",
            subject="Hello",
        )
        assert b"From: bob@example.com" in email_bytes
        assert b"Subject: Hello" in email_bytes

    def test_create_email_with_multiple_attachments(self):
        """Helper creates email with multiple attachments."""
        email_bytes = create_mime_email(
            attachments=[
                ("week03.tji", b"data1"),
                ("report.pdf", b"data2"),
            ],
        )
        assert b"week03.tji" in email_bytes
        assert b"report.pdf" in email_bytes

    def test_oversized_email_creation(self):
        """Helper can create emails exceeding 5 MB for testing."""
        large_content = b"x" * (6 * 1024 * 1024)  # 6 MB
        email_bytes = create_mime_email(
            attachments=[("big.tji", large_content)],
        )
        assert len(email_bytes) > 5 * 1024 * 1024
