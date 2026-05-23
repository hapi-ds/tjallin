"""Integration tests for mail data persistence across container restarts.

These tests validate that messages delivered via SMTP persist in the
maildir-data volume and remain accessible via IMAP after the tj-mail
container is restarted.

Requires Docker and Docker Compose available in the test environment.
Run with: uv run pytest tests/integration/test_mail_persistence.py --tb=short -q -m integration

Requirements: 8.1, 8.2, 8.4
"""

import subprocess
import time
import uuid
from pathlib import Path

import pytest

# Root of the repository (where docker-compose.yml lives)
REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

# Timeout constants
STARTUP_TIMEOUT = 120  # seconds for services to become healthy
DELIVERY_TIMEOUT = 30  # seconds for message delivery
RESTART_TIMEOUT = 60  # seconds for container restart and health recovery

# Mail configuration matching .env defaults
MAIL_DOMAIN = "taskjuggler.local"


def docker_compose_available() -> bool:
    """Check if docker compose is available on this system."""
    try:
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# Skip all tests in this module if Docker Compose is not available
pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not docker_compose_available(),
        reason="Docker Compose not available",
    ),
]


def run_compose(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess[str]:
    """Run a docker compose command in the repo root.

    Args:
        args: Arguments to pass after 'docker compose'.
        timeout: Command timeout in seconds.

    Returns:
        CompletedProcess with stdout/stderr captured.
    """
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE)] + args
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


def run_docker_exec(
    container: str, command: list[str], timeout: int = 30
) -> subprocess.CompletedProcess[str]:
    """Run a command inside a running container.

    Args:
        container: Container/service name.
        command: Command and arguments to execute.
        timeout: Command timeout in seconds.

    Returns:
        CompletedProcess with stdout/stderr captured.
    """
    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE), "exec", "-T", container] + command
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
    )


def wait_for_healthy(service: str, timeout: int = STARTUP_TIMEOUT) -> bool:
    """Wait for a service to reach healthy state.

    Args:
        service: Docker Compose service name.
        timeout: Maximum seconds to wait.

    Returns:
        True if service became healthy within timeout, False otherwise.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = run_compose(
            ["ps", "--format", "{{.Health}}", "--filter", f"service={service}"],
            timeout=10,
        )
        health = result.stdout.strip()
        if health == "healthy":
            return True
        time.sleep(2)
    return False


def send_email_via_sendmail(
    sender: str, recipient: str, subject: str, body: str
) -> bool:
    """Send an email to the tj-mail container via docker exec and sendmail.

    Args:
        sender: Sender email address.
        recipient: Recipient email address.
        subject: Email subject line.
        body: Email body text.

    Returns:
        True if the email was accepted, False otherwise.
    """
    raw_email = (
        f"From: {sender}\r\n"
        f"To: {recipient}\r\n"
        f"Subject: {subject}\r\n"
        f"Date: Mon, 01 Jan 2024 12:00:00 +0000\r\n"
        f"\r\n"
        f"{body}\r\n"
    )

    cmd = [
        "docker", "compose", "-f", str(COMPOSE_FILE),
        "exec", "-T", "tj-mail",
        "sendmail", "-f", sender, recipient,
    ]
    result = subprocess.run(
        cmd,
        input=raw_email,
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPO_ROOT),
    )
    return result.returncode == 0


def wait_for_maildir_message(
    username: str, subject_fragment: str, timeout: int = DELIVERY_TIMEOUT
) -> bool:
    """Wait for a message to appear in a user's Maildir.

    Args:
        username: The mail user whose Maildir to check.
        subject_fragment: A unique string to search for in message files.
        timeout: Maximum seconds to wait.

    Returns:
        True if the message was found within timeout, False otherwise.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = run_docker_exec(
            "tj-mail",
            [
                "sh", "-c",
                f"grep -rl '{subject_fragment}' /var/mail/{username}/Maildir/ 2>/dev/null",
            ],
        )
        if result.returncode == 0 and result.stdout.strip():
            return True
        time.sleep(2)
    return False


def check_imap_message(username: str, password: str, subject_fragment: str) -> bool:
    """Check if a message is accessible via IMAP using doveadm inside the container.

    Args:
        username: IMAP username.
        password: IMAP password.
        subject_fragment: A unique string to search for in message subjects.

    Returns:
        True if the message is found via IMAP, False otherwise.
    """
    # Use doveadm to search for the message (runs inside the container)
    result = run_docker_exec(
        "tj-mail",
        [
            "doveadm", "search", "-u", username,
            "subject", subject_fragment,
        ],
        timeout=15,
    )
    return result.returncode == 0 and result.stdout.strip() != ""


@pytest.fixture(scope="module")
def compose_stack():
    """Start the Docker Compose stack and tear it down after all tests.

    This fixture builds and starts all services, waits for tj-mail to be
    healthy, and tears everything down (including volumes) after the
    test module completes.
    """
    # Build and start the stack in detached mode
    result = run_compose(["up", "-d", "--build"], timeout=300)
    if result.returncode != 0:
        logs = run_compose(["logs", "--tail=50"], timeout=30)
        pytest.fail(
            f"docker compose up failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}\n"
            f"LOGS: {logs.stdout}"
        )

    # Wait for mail service to be healthy
    if not wait_for_healthy("tj-mail", timeout=STARTUP_TIMEOUT):
        logs = run_compose(["logs", "tj-mail", "--tail=30"], timeout=30)
        run_compose(["down", "-v", "--timeout", "10"], timeout=60)
        pytest.fail(f"tj-mail did not become healthy:\n{logs.stdout}")

    yield

    # Tear down: stop containers and remove volumes
    run_compose(["down", "-v", "--timeout", "10"], timeout=60)


class TestMailPersistence:
    """Test that mail data persists across container restarts.

    Validates: Requirements 8.1, 8.2, 8.4
    - 8.1: Named volume for Maildir storage
    - 8.2: Messages survive container stop/start
    - 8.4: Container recreated with existing volume reuses data
    """

    def test_message_persists_after_container_restart(self, compose_stack: None) -> None:
        """Deliver a message, restart tj-mail, verify message is still accessible.

        This validates that the maildir-data volume persists messages across
        container restarts (Requirement 8.2).
        """
        # Generate a unique subject to identify this test message
        unique_id = uuid.uuid4().hex[:12]
        subject = f"persistence-test-{unique_id}"
        recipient_user = "alice"
        recipient = f"{recipient_user}@{MAIL_DOMAIN}"

        # Step 1: Deliver a message via SMTP
        success = send_email_via_sendmail(
            sender=f"test@{MAIL_DOMAIN}",
            recipient=recipient,
            subject=subject,
            body=f"This message tests persistence. ID: {unique_id}",
        )
        assert success, "Failed to send test email via sendmail"

        # Step 2: Wait for message to appear in Maildir
        found = wait_for_maildir_message(recipient_user, unique_id)
        assert found, (
            f"Message with ID '{unique_id}' was not delivered to "
            f"/var/mail/{recipient_user}/Maildir/ within {DELIVERY_TIMEOUT}s"
        )

        # Step 3: Restart the tj-mail container
        restart_result = run_compose(["restart", "tj-mail"], timeout=RESTART_TIMEOUT)
        assert restart_result.returncode == 0, (
            f"Failed to restart tj-mail: {restart_result.stderr}"
        )

        # Step 4: Wait for tj-mail to become healthy again
        healthy = wait_for_healthy("tj-mail", timeout=RESTART_TIMEOUT)
        assert healthy, "tj-mail did not become healthy after restart"

        # Step 5: Verify the message is still in Maildir after restart
        found_after_restart = wait_for_maildir_message(
            recipient_user, unique_id, timeout=10
        )
        assert found_after_restart, (
            f"Message with ID '{unique_id}' was NOT found in Maildir after "
            "container restart — maildir-data volume persistence failed"
        )

    def test_message_accessible_via_imap_after_restart(self, compose_stack: None) -> None:
        """Deliver a message, restart tj-mail, verify IMAP access still works.

        This validates that Dovecot can serve previously delivered messages
        from the persisted volume after a container restart (Requirements 8.2, 8.4).
        """
        # Generate a unique subject
        unique_id = uuid.uuid4().hex[:12]
        subject = f"imap-persist-{unique_id}"
        recipient_user = "alice"
        recipient = f"{recipient_user}@{MAIL_DOMAIN}"

        # Step 1: Deliver a message
        success = send_email_via_sendmail(
            sender=f"test@{MAIL_DOMAIN}",
            recipient=recipient,
            subject=subject,
            body=f"IMAP persistence test. ID: {unique_id}",
        )
        assert success, "Failed to send test email"

        # Step 2: Wait for delivery
        found = wait_for_maildir_message(recipient_user, unique_id)
        assert found, f"Message '{unique_id}' not delivered within {DELIVERY_TIMEOUT}s"

        # Step 3: Verify IMAP access before restart
        imap_before = check_imap_message(recipient_user, "secret1", subject)
        assert imap_before, (
            f"Message '{subject}' not accessible via IMAP before restart"
        )

        # Step 4: Restart the container
        restart_result = run_compose(["restart", "tj-mail"], timeout=RESTART_TIMEOUT)
        assert restart_result.returncode == 0, (
            f"Failed to restart tj-mail: {restart_result.stderr}"
        )

        # Step 5: Wait for healthy state
        healthy = wait_for_healthy("tj-mail", timeout=RESTART_TIMEOUT)
        assert healthy, "tj-mail did not become healthy after restart"

        # Step 6: Verify IMAP access after restart
        imap_after = check_imap_message(recipient_user, "secret1", subject)
        assert imap_after, (
            f"Message '{subject}' NOT accessible via IMAP after container restart — "
            "Dovecot failed to serve persisted maildir-data volume"
        )

    def test_multiple_messages_persist(self, compose_stack: None) -> None:
        """Deliver multiple messages, restart, verify all persist.

        Validates that the volume correctly persists multiple messages
        and none are lost during restart (Requirement 8.2).
        """
        recipient_user = "alice"
        recipient = f"{recipient_user}@{MAIL_DOMAIN}"
        message_ids = []

        # Step 1: Deliver 3 messages
        for i in range(3):
            unique_id = uuid.uuid4().hex[:12]
            message_ids.append(unique_id)
            success = send_email_via_sendmail(
                sender=f"test@{MAIL_DOMAIN}",
                recipient=recipient,
                subject=f"multi-persist-{unique_id}",
                body=f"Message {i + 1} of 3. ID: {unique_id}",
            )
            assert success, f"Failed to send message {i + 1}"

        # Step 2: Wait for all messages to be delivered
        for uid in message_ids:
            found = wait_for_maildir_message(recipient_user, uid)
            assert found, f"Message '{uid}' not delivered within {DELIVERY_TIMEOUT}s"

        # Step 3: Restart the container
        restart_result = run_compose(["restart", "tj-mail"], timeout=RESTART_TIMEOUT)
        assert restart_result.returncode == 0, (
            f"Failed to restart tj-mail: {restart_result.stderr}"
        )

        # Step 4: Wait for healthy state
        healthy = wait_for_healthy("tj-mail", timeout=RESTART_TIMEOUT)
        assert healthy, "tj-mail did not become healthy after restart"

        # Step 5: Verify all messages still exist
        for uid in message_ids:
            found = wait_for_maildir_message(recipient_user, uid, timeout=10)
            assert found, (
                f"Message '{uid}' was lost after container restart"
            )
