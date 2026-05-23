"""Integration tests for SMTP mail delivery to local Maildir.

These tests validate that the mail service accepts messages via SMTP
and delivers them to the recipient's Maildir storage.

Requires a running Docker Compose stack with the tj-mail service.
Run with: uv run pytest tests/integration/test_mail_delivery.py --tb=short -q -m integration

Requirements: 1.2, 1.4
"""

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


class TestLocalMailDelivery:
    """Test SMTP delivery to local users at TJ_MAIL_DOMAIN.

    Validates: Requirements 1.2, 1.4
    - Messages addressed to local domain users are delivered to Maildir.
    - Messages addressed to any user at TJ_MAIL_DOMAIN are stored locally.
    """

    def test_send_email_to_local_user(self, mail_config: MailConfig) -> None:
        """Send an email via SMTP to a local user and verify acceptance.

        The SMTP server should accept the message for delivery to a
        configured user at the local domain.
        """
        # Pick the first configured user
        username = next(iter(mail_config.users))
        recipient = f"{username}@{mail_config.domain}"
        sender = f"test@{mail_config.domain}"
        unique_subject = f"Test delivery {uuid.uuid4().hex[:8]}"

        msg = MIMEText("This is a test message for local delivery.")
        msg["Subject"] = unique_subject
        msg["From"] = sender
        msg["To"] = recipient

        # Send via SMTP — should be accepted without error
        with smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=10) as smtp:
            smtp.sendmail(sender, [recipient], msg.as_string())

        # Allow time for delivery to Maildir
        time.sleep(2)

    def test_send_email_to_multiple_recipients(self, mail_config: MailConfig) -> None:
        """Send an email to multiple local recipients and verify acceptance.

        The SMTP server should accept the message for delivery to all
        configured users at the local domain.
        """
        if len(mail_config.users) < 2:
            pytest.skip("Need at least 2 configured users for multi-recipient test")

        users = list(mail_config.users.keys())[:2]
        recipients = [f"{u}@{mail_config.domain}" for u in users]
        sender = f"test@{mail_config.domain}"
        unique_subject = f"Test multi-recipient {uuid.uuid4().hex[:8]}"

        msg = MIMEText("This is a test message for multiple recipients.")
        msg["Subject"] = unique_subject
        msg["From"] = sender
        msg["To"] = ", ".join(recipients)

        # Send via SMTP — should be accepted for all recipients
        with smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=10) as smtp:
            result = smtp.sendmail(sender, recipients, msg.as_string())

        # sendmail returns a dict of failed recipients; should be empty
        assert result == {}, f"Some recipients were rejected: {result}"

        # Allow time for delivery
        time.sleep(2)

    def test_delivered_message_appears_in_maildir(self, mail_config: MailConfig) -> None:
        """Send an email and verify it appears in the user's Maildir via IMAP.

        This confirms end-to-end delivery: SMTP acceptance → Maildir storage → IMAP retrieval.
        """
        import imaplib

        username = next(iter(mail_config.users))
        password = mail_config.users[username]
        recipient = f"{username}@{mail_config.domain}"
        sender = f"test@{mail_config.domain}"
        unique_subject = f"Delivery check {uuid.uuid4().hex[:8]}"

        msg = MIMEText("Verifying Maildir delivery via IMAP.")
        msg["Subject"] = unique_subject
        msg["From"] = sender
        msg["To"] = recipient

        # Send the message
        with smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=10) as smtp:
            smtp.sendmail(sender, [recipient], msg.as_string())

        # Wait for delivery
        time.sleep(3)

        # Verify via IMAP that the message arrived
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
        finally:
            try:
                imap.logout()
            except Exception:
                pass
