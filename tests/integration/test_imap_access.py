"""Integration tests for IMAP access to the mail service.

These tests validate that mail clients can connect via IMAP, authenticate,
list folders, and fetch delivered messages.

Requires a running Docker Compose stack with the tj-mail service.
Run with: uv run pytest tests/integration/test_imap_access.py --tb=short -q -m integration

Requirements: 2.2, 2.3, 2.5, 2.6
"""

import imaplib
import smtplib
import time
import uuid
from email.mime.text import MIMEText

import pytest

from .conftest import MailConfig, docker_compose_available, mail_service_running

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not docker_compose_available(),
        reason="Docker Compose not available",
    ),
    pytest.mark.skipif(
        not mail_service_running(),
        reason="tj-mail service not running or not healthy",
    ),
]


class TestIMAPAuthentication:
    """Test IMAP authentication with valid and invalid credentials.

    Validates: Requirements 2.2, 2.5
    - Valid credentials grant access to the mailbox.
    - Invalid credentials are rejected with authentication failure.
    """

    def test_login_with_valid_credentials(self, mail_config: MailConfig) -> None:
        """Connect via IMAP with valid credentials and verify successful login.

        The IMAP server should authenticate the user and allow mailbox access.
        """
        username = next(iter(mail_config.users))
        password = mail_config.users[username]

        imap = imaplib.IMAP4(mail_config.imap_host, mail_config.imap_port)
        try:
            # Login should succeed without raising an exception
            status, response = imap.login(username, password)
            assert status == "OK", f"Login failed with status: {status}"
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def test_login_with_invalid_password(self, mail_config: MailConfig) -> None:
        """Attempt IMAP login with wrong password and verify rejection.

        The IMAP server should reject the connection with an authentication
        failure response (IMAP NO).
        """
        username = next(iter(mail_config.users))
        wrong_password = "definitely_wrong_password_12345"

        imap = imaplib.IMAP4(mail_config.imap_host, mail_config.imap_port)
        try:
            with pytest.raises(imaplib.IMAP4.error):
                imap.login(username, wrong_password)
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def test_login_with_nonexistent_user(self, mail_config: MailConfig) -> None:
        """Attempt IMAP login with a non-existent username and verify rejection.

        The IMAP server should reject authentication for unknown users.
        """
        nonexistent_user = f"nonexistent_{uuid.uuid4().hex[:8]}"

        imap = imaplib.IMAP4(mail_config.imap_host, mail_config.imap_port)
        try:
            with pytest.raises(imaplib.IMAP4.error):
                imap.login(nonexistent_user, "anypassword")
        finally:
            try:
                imap.logout()
            except Exception:
                pass


class TestIMAPFolderListing:
    """Test IMAP folder listing functionality.

    Validates: Requirement 2.3
    - The IMAP server returns at minimum the standard INBOX folder.
    """

    def test_list_folders_includes_inbox(self, mail_config: MailConfig) -> None:
        """List IMAP folders and verify INBOX is present.

        The IMAP server should return at minimum the standard INBOX folder
        containing delivered messages.
        """
        username = next(iter(mail_config.users))
        password = mail_config.users[username]

        imap = imaplib.IMAP4(mail_config.imap_host, mail_config.imap_port)
        try:
            imap.login(username, password)

            # List all folders
            status, folder_data = imap.list()
            assert status == "OK", f"LIST command failed: {status}"

            # Parse folder names from response
            folder_names = []
            for item in folder_data:
                if item:
                    # IMAP LIST response format: (flags) "delimiter" "name"
                    decoded = item.decode() if isinstance(item, bytes) else str(item)
                    folder_names.append(decoded)

            # INBOX should be present (case-insensitive check)
            inbox_found = any("INBOX" in name.upper() for name in folder_names)
            assert inbox_found, (
                f"INBOX not found in folder listing. Folders: {folder_names}"
            )
        finally:
            try:
                imap.logout()
            except Exception:
                pass

    def test_select_inbox(self, mail_config: MailConfig) -> None:
        """Select the INBOX folder and verify it can be opened.

        The IMAP server should allow selecting INBOX for message access.
        """
        username = next(iter(mail_config.users))
        password = mail_config.users[username]

        imap = imaplib.IMAP4(mail_config.imap_host, mail_config.imap_port)
        try:
            imap.login(username, password)

            status, data = imap.select("INBOX")
            assert status == "OK", f"SELECT INBOX failed: {status}"

            # data[0] contains the message count (may be b'0' if empty)
            message_count = int(data[0])
            assert message_count >= 0, "Invalid message count"
        finally:
            try:
                imap.logout()
            except Exception:
                pass


class TestIMAPMessageFetch:
    """Test fetching messages via IMAP after SMTP delivery.

    Validates: Requirement 2.6
    - Messages delivered via SMTP can be retrieved via IMAP with matching
      subject, sender, and body content.
    """

    def test_fetch_delivered_message(self, mail_config: MailConfig) -> None:
        """Send a message via SMTP and fetch it via IMAP, verifying content matches.

        This validates the full SMTP-to-IMAP round-trip: the message subject,
        sender, and body should all be retrievable via IMAP.
        """
        username = next(iter(mail_config.users))
        password = mail_config.users[username]
        recipient = f"{username}@{mail_config.domain}"
        sender = f"integration-test@{mail_config.domain}"
        unique_subject = f"IMAP fetch test {uuid.uuid4().hex[:8]}"
        body_text = f"Test body content {uuid.uuid4().hex[:8]}"

        # Step 1: Send message via SMTP
        msg = MIMEText(body_text)
        msg["Subject"] = unique_subject
        msg["From"] = sender
        msg["To"] = recipient

        with smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=10) as smtp:
            smtp.sendmail(sender, [recipient], msg.as_string())

        # Wait for delivery to Maildir
        time.sleep(3)

        # Step 2: Fetch via IMAP and verify content
        imap = imaplib.IMAP4(mail_config.imap_host, mail_config.imap_port)
        try:
            imap.login(username, password)
            imap.select("INBOX")

            # Search for the message by subject
            status, data = imap.search(None, "SUBJECT", f'"{unique_subject}"')
            assert status == "OK", f"IMAP search failed: {status}"

            message_ids = data[0].split()
            assert len(message_ids) >= 1, (
                f"Message with subject '{unique_subject}' not found in INBOX"
            )

            # Fetch the most recent matching message
            msg_id = message_ids[-1]
            status, msg_data = imap.fetch(msg_id, "(RFC822)")
            assert status == "OK", f"IMAP fetch failed: {status}"

            # Parse the fetched message
            raw_email = msg_data[0][1]
            email_content = raw_email.decode() if isinstance(raw_email, bytes) else raw_email

            # Verify subject, sender, and body are present
            assert unique_subject in email_content, (
                f"Subject '{unique_subject}' not found in fetched message"
            )
            assert sender in email_content, (
                f"Sender '{sender}' not found in fetched message"
            )
            assert body_text in email_content, (
                f"Body text '{body_text}' not found in fetched message"
            )
        finally:
            try:
                imap.logout()
            except Exception:
                pass
