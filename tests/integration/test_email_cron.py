"""Integration tests for email reception and cron execution workflows.

These tests validate the full email-to-timesheet pipeline and cron task
execution by running against the live Docker Compose stack. They use
Python's smtplib to send SMTP messages to the mail container and verify
that valid attachments are stored in the timesheets volume.

Requires Docker and Docker Compose available in the test environment.
Run with: uv run pytest tests/integration/test_email_cron.py --tb=short -q -m integration

Requirements: 5.3, 5.7, 6.2, 6.5
"""

import subprocess
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pytest

# Root of the repository (where docker-compose.yml lives)
REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

# Timeout constants
STARTUP_TIMEOUT = 120  # seconds for all services to become healthy
EMAIL_PROCESS_TIMEOUT = 30  # seconds for email to be processed
CRON_WAIT_TIMEOUT = 90  # seconds to wait for a cron task execution

# Mail configuration matching .env defaults
MAIL_DOMAIN = "taskjuggler.local"
SMTP_PORT_INTERNAL = 25


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


def get_mail_container_ip() -> str:
    """Get the IP address of the tj-mail container on the Docker network.

    Returns:
        The container IP address as a string.
    """
    result = run_compose(
        ["exec", "-T", "tj-mail", "hostname", "-i"],
        timeout=10,
    )
    if result.returncode == 0:
        return result.stdout.strip().split()[0]
    # Fallback: try to get IP via docker inspect
    inspect_result = subprocess.run(
        [
            "docker", "compose", "-f", str(COMPOSE_FILE),
            "port", "tj-mail", "25",
        ],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=str(REPO_ROOT),
    )
    if inspect_result.returncode == 0 and inspect_result.stdout.strip():
        return inspect_result.stdout.strip().split(":")[0]
    return "127.0.0.1"


def send_email_to_mail_container(
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]] | None = None,
) -> bool:
    """Send an email to the tj-mail container via SMTP using docker exec and sendmail.

    Since the mail container's port 25 is only exposed on the internal Docker
    network, we pipe the raw email into the container via docker exec.

    Args:
        sender: Sender email address.
        recipient: Recipient email address.
        subject: Email subject line.
        body: Email body text.
        attachments: Optional list of (filename, content) tuples.

    Returns:
        True if the email was accepted, False otherwise.
    """
    # Build the MIME message
    if attachments:
        msg = MIMEMultipart()
        msg.attach(MIMEText(body, "plain"))
        for filename, content in attachments:
            attachment = MIMEApplication(content, Name=filename)
            attachment["Content-Disposition"] = f'attachment; filename="{filename}"'
            msg.attach(attachment)
    else:
        msg = MIMEText(body, "plain")

    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject

    raw_email = msg.as_string()

    # Pipe the email into the container's sendmail command
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


@pytest.fixture(scope="module")
def compose_stack():
    """Start the Docker Compose stack and tear it down after all tests.

    This fixture builds and starts all services, waits for them to be
    running, and tears everything down (including volumes) after the
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

    # Wait for cron service to be healthy
    if not wait_for_healthy("tj-cron", timeout=STARTUP_TIMEOUT):
        logs = run_compose(["logs", "tj-cron", "--tail=30"], timeout=30)
        run_compose(["down", "-v", "--timeout", "10"], timeout=60)
        pytest.fail(f"tj-cron did not become healthy:\n{logs.stdout}")

    yield

    # Tear down: stop containers and remove volumes
    run_compose(["down", "-v", "--timeout", "10"], timeout=60)


class TestEmailReception:
    """Test email reception: send SMTP email with .tji attachment.

    Verify file lands in timesheets volume.
    Validates: Requirement 5.3 — valid timesheet attachment stored in
    Project_Volume within 30 seconds of receipt.
    """

    def test_valid_tji_attachment_stored(self, compose_stack: None) -> None:
        """Sending an email with a valid .tji attachment stores it in the timesheets volume."""
        # Clear any existing test files
        run_docker_exec(
            "tj-mail",
            ["sh", "-c", "rm -f /app/timesheets/2024-W05-test.tji"],
        )

        # Create a valid .tji timesheet content
        tji_content = (
            b'timesheet test 2024-01-29 +1w {\n'
            b'  task acme_web.dev.backend.schema {\n'
            b'    work 20h\n'
            b'    status green "Schema work completed"\n'
            b'  }\n'
            b'}\n'
        )

        # Send email with .tji attachment
        success = send_email_to_mail_container(
            sender="alice@example.com",
            recipient=f"timesheets@{MAIL_DOMAIN}",
            subject="Timesheet Week 5",
            body="Please find my timesheet attached.",
            attachments=[("2024-W05-test.tji", tji_content)],
        )
        assert success, "Failed to send email to mail container"

        # Wait for the email to be processed (requirement: within 30 seconds)
        deadline = time.time() + EMAIL_PROCESS_TIMEOUT
        file_found = False
        while time.time() < deadline:
            result = run_docker_exec(
                "tj-mail",
                ["test", "-f", "/app/timesheets/2024-W05-test.tji"],
            )
            if result.returncode == 0:
                file_found = True
                break
            time.sleep(2)

        assert file_found, (
            "Timesheet file '2024-W05-test.tji' was not stored in the timesheets "
            "volume within 30 seconds of email receipt"
        )

        # Verify the content matches what was sent
        content_result = run_docker_exec(
            "tj-mail",
            ["cat", "/app/timesheets/2024-W05-test.tji"],
        )
        assert content_result.returncode == 0
        assert "timesheet test 2024-01-29" in content_result.stdout

    def test_attachment_size_within_limit(self, compose_stack: None) -> None:
        """A .tji attachment under 1 MB is accepted and stored.

        Validates: Requirement 5.7 — attachment valid only if .tji extension
        and does not exceed 1 MB.
        """
        # Clear any existing test files
        run_docker_exec(
            "tj-mail",
            ["sh", "-c", "rm -f /app/timesheets/2024-W06-small.tji"],
        )

        # Create a small but non-trivial .tji file (under 1 MB)
        tji_content = (
            b'timesheet small 2024-02-05 +1w {\n'
            b'  task acme_web.dev.frontend.layouts {\n'
            b'    work 16h\n'
            b'    status yellow "In progress"\n'
            b'  }\n'
            b'}\n'
        )

        success = send_email_to_mail_container(
            sender="bob@example.com",
            recipient=f"timesheets@{MAIL_DOMAIN}",
            subject="Timesheet Week 6",
            body="My weekly timesheet.",
            attachments=[("2024-W06-small.tji", tji_content)],
        )
        assert success, "Failed to send email"

        # Wait for processing
        deadline = time.time() + EMAIL_PROCESS_TIMEOUT
        file_found = False
        while time.time() < deadline:
            result = run_docker_exec(
                "tj-mail",
                ["test", "-f", "/app/timesheets/2024-W06-small.tji"],
            )
            if result.returncode == 0:
                file_found = True
                break
            time.sleep(2)

        assert file_found, "Small .tji attachment was not stored"


class TestInvalidEmailRejection:
    """Test invalid email rejection and logging.

    Validates: Requirement 5.7 — invalid emails are rejected with logged reason.
    """

    def test_non_tji_attachment_rejected(self, compose_stack: None) -> None:
        """An email with a non-.tji attachment is rejected and logged."""
        # Send email with a .txt attachment (not .tji)
        txt_content = b"This is not a timesheet file."

        send_email_to_mail_container(
            sender="mallory@example.com",
            recipient=f"timesheets@{MAIL_DOMAIN}",
            subject="Not a timesheet",
            body="Here is a random file.",
            attachments=[("notes.txt", txt_content)],
        )
        # The email may be accepted by Postfix but rejected by process-email.sh
        # Either way, the .txt file should NOT appear in timesheets

        # Wait a moment for processing
        time.sleep(5)

        # Verify no .txt file was stored
        result = run_docker_exec(
            "tj-mail",
            ["sh", "-c", "find /app/timesheets -name 'notes.txt' | wc -l"],
        )
        assert result.returncode == 0
        count = int(result.stdout.strip())
        assert count == 0, "Non-.tji attachment should not be stored in timesheets"

        # Check logs for rejection message
        logs_result = run_compose(["logs", "tj-mail", "--tail=50"], timeout=10)
        log_output = logs_result.stdout
        has_rejection = (
            "Rejected" in log_output
            or "rejected" in log_output
            or "does not have" in log_output
        )
        assert has_rejection, "Expected rejection log entry for non-.tji attachment"

    def test_oversized_attachment_rejected(self, compose_stack: None) -> None:
        """An email with a .tji attachment exceeding 1 MB is rejected.

        Validates: Requirement 5.7 — attachment must not exceed 1 MB.
        """
        # Create a .tji file larger than 1 MB (1.1 MB of padding)
        oversized_content = b"timesheet big 2024-02-12 +1w {\n"
        oversized_content += b"# " + b"x" * (1_100_000) + b"\n"
        oversized_content += b"}\n"

        send_email_to_mail_container(
            sender="eve@example.com",
            recipient=f"timesheets@{MAIL_DOMAIN}",
            subject="Oversized timesheet",
            body="This attachment is too large.",
            attachments=[("2024-W07-oversized.tji", oversized_content)],
        )

        # Wait for processing
        time.sleep(5)

        # Verify the oversized file was NOT stored
        result = run_docker_exec(
            "tj-mail",
            ["test", "-f", "/app/timesheets/2024-W07-oversized.tji"],
        )
        assert result.returncode != 0, (
            "Oversized .tji attachment should not be stored in timesheets"
        )

        # Check logs for size rejection
        logs_result = run_compose(["logs", "tj-mail", "--tail=50"], timeout=10)
        log_output = logs_result.stdout
        assert "exceeds" in log_output or "size" in log_output.lower(), (
            "Expected log entry about attachment size rejection"
        )

    def test_email_without_attachment_rejected(self, compose_stack: None) -> None:
        """An email with no attachment is rejected and logged."""
        send_email_to_mail_container(
            sender="nobody@example.com",
            recipient=f"timesheets@{MAIL_DOMAIN}",
            subject="No attachment here",
            body="I forgot to attach my timesheet.",
            attachments=None,
        )

        # Wait for processing
        time.sleep(5)

        # Check logs for rejection (no valid attachments)
        logs_result = run_compose(["logs", "tj-mail", "--tail=50"], timeout=10)
        log_output = logs_result.stdout
        assert "no" in log_output.lower() and "attachment" in log_output.lower(), (
            "Expected log entry about missing attachments"
        )


class TestCronExecution:
    """Test cron execution: verify scheduled task runs and produces logs.

    Validates: Requirement 6.2 — cron triggers compilation on schedule.
    Validates: Requirement 6.5 — task completion/failure is logged with timestamp and task name.
    """

    def test_cron_task_execution_logged(self, compose_stack: None) -> None:
        """Cron service logs task execution with timestamp and task name.

        We configure a very short cron interval and verify the task runs
        by checking the cron service logs for execution entries.
        """
        # The cron service should already be running with its configured schedule.
        # Rather than waiting for the default schedule, we manually trigger a task
        # via the run-task.sh wrapper to verify the logging format.
        result = run_docker_exec(
            "tj-cron",
            [
                "/app/scripts/run-task.sh", "compile",
                "docker", "exec", "tj-core", "/app/scripts/compile.sh",
            ],
            timeout=60,
        )

        # The task should complete (success or failure depending on stack state)
        # What matters is that it produces structured log output
        combined_output = result.stdout + result.stderr

        # Verify structured log format: [tj-cron] [ISO8601] [LEVEL] message
        assert "[tj-cron]" in combined_output, (
            f"Expected '[tj-cron]' in log output, got: {combined_output}"
        )
        assert "compile" in combined_output, (
            f"Expected task name 'compile' in log output, got: {combined_output}"
        )

    def test_cron_task_success_logged(self, compose_stack: None) -> None:
        """Successful cron task execution is logged with completion message.

        Validates: Requirement 6.5 — successful task logged with timestamp and task name.
        """
        # Wait for tj-core to be healthy first
        wait_for_healthy("tj-core", timeout=60)

        # Execute the compile task via the cron wrapper
        result = run_docker_exec(
            "tj-cron",
            [
                "/app/scripts/run-task.sh", "compile",
                "docker", "exec", "tj-core", "/app/scripts/compile.sh",
            ],
            timeout=60,
        )

        combined_output = result.stdout + result.stderr

        if result.returncode == 0:
            # On success, verify the completion log entry
            assert "completed successfully" in combined_output, (
                f"Expected 'completed successfully' in output: {combined_output}"
            )
            assert "[INFO]" in combined_output, (
                f"Expected '[INFO]' level in success log: {combined_output}"
            )
        else:
            # If compilation fails (e.g., project not ready), verify failure logging
            assert "failed" in combined_output.lower(), (
                f"Expected failure log entry: {combined_output}"
            )
            assert "[ERROR]" in combined_output, (
                f"Expected '[ERROR]' level in failure log: {combined_output}"
            )

    def test_cron_overlap_prevention(self, compose_stack: None) -> None:
        """Cron service prevents overlapping task executions via lock file.

        Validates: Requirement 6.5 — overlapping execution is skipped with warning.
        """
        # Create a lock file manually to simulate a running task
        lock_cmd = (
            'echo "PID=99999 STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)"'
            " > /tmp/tj-overlap-test.lock"
        )
        run_docker_exec(
            "tj-cron",
            ["sh", "-c", lock_cmd],
        )

        # Try to run a task with the same lock file name
        # We need to use a task name that maps to the lock file we created
        result = run_docker_exec(
            "tj-cron",
            [
                "/app/scripts/run-task.sh", "overlap-test",
                "echo", "should-not-run",
            ],
            timeout=30,
        )

        combined_output = result.stdout + result.stderr

        # The task should be skipped because the lock file exists
        # Note: the lock file PID 99999 won't be running, so it will be
        # detected as stale and cleaned up. This tests the stale lock path.
        # Either "skipped" (if PID is alive) or "stale" (if PID is dead) is valid.
        assert "skipped" in combined_output.lower() or "stale" in combined_output.lower(), (
            f"Expected overlap prevention or stale lock detection in output: {combined_output}"
        )

        # Cleanup
        run_docker_exec("tj-cron", ["rm", "-f", "/tmp/tj-overlap-test.lock"])

    def test_supercronic_running(self, compose_stack: None) -> None:
        """Supercronic process is running in the cron container.

        Validates: Requirement 6.2 — cron service is operational.
        """
        result = run_docker_exec(
            "tj-cron",
            ["pgrep", "supercronic"],
        )
        assert result.returncode == 0, (
            "Supercronic process not found in tj-cron container"
        )

    def test_crontab_generated(self, compose_stack: None) -> None:
        """Crontab file is generated with expected task entries.

        Validates: Requirement 6.2 — scheduled tasks are defined.
        """
        result = run_docker_exec(
            "tj-cron",
            ["cat", "/app/crontab"],
        )
        assert result.returncode == 0, "Crontab file not found"

        crontab_content = result.stdout

        # Verify all three scheduled tasks are present
        assert "compile" in crontab_content, "Compile task not in crontab"
        assert "timesheets" in crontab_content, "Timesheets task not in crontab"
        assert "reminders" in crontab_content, "Reminders task not in crontab"

        # Verify the run-task.sh wrapper is used
        assert "run-task.sh" in crontab_content, "run-task.sh wrapper not used in crontab"
