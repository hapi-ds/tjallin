"""Integration tests for SMTP rejection scenarios.

These tests validate that the SMTP server correctly rejects messages
that violate delivery rules: non-local domains, unknown users, and
oversized messages.

Requires a running Docker Compose stack with the tj-mail service.
Run with: uv run pytest tests/integration/test_smtp_rejection.py --tb=short -q -m integration

Requirements: 1.5, 1.6, 1.7
"""

import smtplib
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


class TestNonLocalDomainRejection:
    """Test that messages to non-local domains are rejected with 554.

    Validates: Requirement 1.5
    - Messages addressed to a domain other than TJ_MAIL_DOMAIN are rejected
      with SMTP reply code 554.
    """

    def test_reject_external_domain(self, mail_config: MailConfig) -> None:
        """Send to a non-local domain and expect 554 rejection.

        The SMTP server should reject messages addressed to external domains
        since no relay is configured.
        """
        sender = f"test@{mail_config.domain}"
        external_recipient = "user@external-domain.com"

        msg = MIMEText("This should be rejected — external domain.")
        msg["Subject"] = f"External domain test {uuid.uuid4().hex[:8]}"
        msg["From"] = sender
        msg["To"] = external_recipient

        with smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=10) as smtp:
            with pytest.raises(smtplib.SMTPRecipientsRefused) as exc_info:
                smtp.sendmail(sender, [external_recipient], msg.as_string())

            # Verify the rejection code is 554 (relay access denied)
            refused = exc_info.value.recipients
            assert external_recipient in refused, (
                f"Expected {external_recipient} in refused recipients"
            )
            error_code = refused[external_recipient][0]
            assert error_code == 554, (
                f"Expected SMTP 554 for non-local domain, got {error_code}"
            )

    def test_reject_another_external_domain(self, mail_config: MailConfig) -> None:
        """Send to a different non-local domain and expect 554 rejection.

        Confirms the rejection applies to any non-local domain, not just
        a specific one.
        """
        sender = f"test@{mail_config.domain}"
        external_recipient = f"someone@random-{uuid.uuid4().hex[:6]}.org"

        msg = MIMEText("This should also be rejected.")
        msg["Subject"] = f"Another external test {uuid.uuid4().hex[:8]}"
        msg["From"] = sender
        msg["To"] = external_recipient

        with smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=10) as smtp:
            with pytest.raises(smtplib.SMTPRecipientsRefused) as exc_info:
                smtp.sendmail(sender, [external_recipient], msg.as_string())

            refused = exc_info.value.recipients
            assert external_recipient in refused
            error_code = refused[external_recipient][0]
            assert error_code == 554, (
                f"Expected SMTP 554 for non-local domain, got {error_code}"
            )


class TestUnknownUserRejection:
    """Test that messages to unknown local users are rejected with 550.

    Validates: Requirement 1.6
    - Messages addressed to a user that does not exist at TJ_MAIL_DOMAIN
      are rejected with SMTP reply code 550.
    """

    def test_reject_unknown_user(self, mail_config: MailConfig) -> None:
        """Send to a non-existent user at the local domain and expect 550 rejection.

        The SMTP server should reject messages to users not configured in
        TJ_MAIL_USERS.
        """
        sender = f"test@{mail_config.domain}"
        unknown_user = f"nonexistent_{uuid.uuid4().hex[:8]}@{mail_config.domain}"

        msg = MIMEText("This should be rejected — unknown user.")
        msg["Subject"] = f"Unknown user test {uuid.uuid4().hex[:8]}"
        msg["From"] = sender
        msg["To"] = unknown_user

        with smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=10) as smtp:
            with pytest.raises(smtplib.SMTPRecipientsRefused) as exc_info:
                smtp.sendmail(sender, [unknown_user], msg.as_string())

            refused = exc_info.value.recipients
            assert unknown_user in refused, (
                f"Expected {unknown_user} in refused recipients"
            )
            error_code = refused[unknown_user][0]
            assert error_code == 550, (
                f"Expected SMTP 550 for unknown user, got {error_code}"
            )

    def test_reject_another_unknown_user(self, mail_config: MailConfig) -> None:
        """Send to a different non-existent user and expect 550 rejection.

        Confirms the rejection applies to any unknown user, not just a
        specific one.
        """
        sender = f"test@{mail_config.domain}"
        unknown_user = f"ghost_{uuid.uuid4().hex[:8]}@{mail_config.domain}"

        msg = MIMEText("This should also be rejected — unknown user.")
        msg["Subject"] = f"Another unknown user test {uuid.uuid4().hex[:8]}"
        msg["From"] = sender
        msg["To"] = unknown_user

        with smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=10) as smtp:
            with pytest.raises(smtplib.SMTPRecipientsRefused) as exc_info:
                smtp.sendmail(sender, [unknown_user], msg.as_string())

            refused = exc_info.value.recipients
            assert unknown_user in refused
            error_code = refused[unknown_user][0]
            assert error_code == 550, (
                f"Expected SMTP 550 for unknown user, got {error_code}"
            )


class TestOversizedMessageRejection:
    """Test that oversized messages are rejected with 552.

    Validates: Requirement 1.7
    - Messages larger than 5,242,880 bytes (5 MB) are rejected with
      SMTP reply code 552.
    """

    def test_reject_oversized_message(self, mail_config: MailConfig) -> None:
        """Send a message exceeding 5 MB and expect 552 rejection.

        The SMTP server should reject messages larger than the configured
        message_size_limit of 5,242,880 bytes.
        """
        username = next(iter(mail_config.users))
        recipient = f"{username}@{mail_config.domain}"
        sender = f"test@{mail_config.domain}"

        # Create a message body larger than 5 MB
        # Use 5.5 MB to clearly exceed the 5 MB limit
        large_body = "X" * (5_500_000)

        msg = MIMEText(large_body)
        msg["Subject"] = f"Oversized message test {uuid.uuid4().hex[:8]}"
        msg["From"] = sender
        msg["To"] = recipient

        with smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=30) as smtp:
            with pytest.raises(smtplib.SMTPDataError) as exc_info:
                smtp.sendmail(sender, [recipient], msg.as_string())

            # Verify the rejection code is 552 (message size exceeded)
            error_code = exc_info.value.smtp_code
            assert error_code == 552, (
                f"Expected SMTP 552 for oversized message, got {error_code}"
            )

    def test_accept_message_just_under_limit(self, mail_config: MailConfig) -> None:
        """Send a message just under 5 MB and verify it is accepted.

        This confirms the size limit is enforced at the correct threshold.
        A message slightly under 5 MB should be accepted for delivery.
        """
        username = next(iter(mail_config.users))
        recipient = f"{username}@{mail_config.domain}"
        sender = f"test@{mail_config.domain}"

        # Create a message body of ~4 MB (well under the 5 MB limit)
        body = "Y" * (4_000_000)

        msg = MIMEText(body)
        msg["Subject"] = f"Under-limit message test {uuid.uuid4().hex[:8]}"
        msg["From"] = sender
        msg["To"] = recipient

        # This should succeed without raising an exception
        with smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=30) as smtp:
            result = smtp.sendmail(sender, [recipient], msg.as_string())

        # sendmail returns empty dict on success
        assert result == {}, f"Message under 5 MB was rejected: {result}"
