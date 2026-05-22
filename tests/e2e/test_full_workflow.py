"""End-to-end tests for the full TaskJuggler Docker Compose workflow.

These tests validate the complete system workflow from stack startup through
report generation, timesheet processing, and manual trigger script execution.
They exercise the full integration path that a real user would follow.

Requires Docker and Docker Compose available in the test environment.
Run with: uv run pytest tests/e2e/test_full_workflow.py --tb=short -q -m integration

Requirements: 7.2, 7.6, 9.9, 10.1, 10.2, 10.3
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
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Timeout constants
FULL_STARTUP_TIMEOUT = 120  # seconds for all health checks to pass
COMPILE_TIMEOUT = 30  # seconds for compilation to complete
HTTP_TIMEOUT = 10  # seconds for HTTP response
EMAIL_PROCESS_TIMEOUT = 30  # seconds for email to be processed

# Mail configuration matching defaults
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


def wait_for_healthy(service: str, timeout: int = FULL_STARTUP_TIMEOUT) -> bool:
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


def send_email_to_mail_container(
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    attachments: list[tuple[str, bytes]] | None = None,
) -> bool:
    """Send an email to the tj-mail container via docker exec and sendmail.

    Args:
        sender: Sender email address.
        recipient: Recipient email address.
        subject: Email subject line.
        body: Email body text.
        attachments: Optional list of (filename, content) tuples.

    Returns:
        True if the email was accepted, False otherwise.
    """
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
    """Start the full Docker Compose stack and tear it down after all tests.

    Builds and starts all services in detached mode, then tears everything
    down (including volumes) after the test module completes.
    """
    # Build and start the full stack
    result = run_compose(["up", "-d", "--build"], timeout=300)
    if result.returncode != 0:
        logs = run_compose(["logs", "--tail=50"], timeout=30)
        pytest.fail(
            f"docker compose up failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}\n"
            f"LOGS: {logs.stdout}"
        )

    yield

    # Tear down: stop containers and remove volumes
    run_compose(["down", "-v", "--timeout", "10"], timeout=60)


class TestFullStackStartup:
    """Test docker compose up with default config — all health checks pass within 120 seconds.

    Validates: Requirement 7.2 — all service health checks pass and web interface
    returns HTTP 200 within 120 seconds of docker compose up completing.
    """

    def test_all_services_healthy_within_120_seconds(self, compose_stack: None) -> None:
        """All four services reach healthy state within 120 seconds."""
        services = ["tj-core", "tj-web", "tj-mail", "tj-cron"]
        unhealthy = []

        for service in services:
            if not wait_for_healthy(service, timeout=FULL_STARTUP_TIMEOUT):
                unhealthy.append(service)

        if unhealthy:
            # Capture logs for debugging
            logs = run_compose(["logs", "--tail=30"], timeout=30)
            pytest.fail(
                f"Services did not reach healthy state within 120 seconds: "
                f"{', '.join(unhealthy)}\nLogs:\n{logs.stdout}"
            )

    def test_web_interface_http_200_within_120_seconds(self, compose_stack: None) -> None:
        """Web interface returns HTTP 200 within 120 seconds of startup.

        Validates: Requirement 7.2 — web interface accessible at default port.
        """
        # Wait for tj-web to be healthy first
        assert wait_for_healthy("tj-web", timeout=FULL_STARTUP_TIMEOUT), (
            "tj-web did not become healthy within 120 seconds"
        )

        # Verify HTTP 200 response
        http_result = run_docker_exec(
            "tj-web",
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:8080/"],
            timeout=HTTP_TIMEOUT,
        )
        assert http_result.returncode == 0, f"curl failed: {http_result.stderr}"
        status_code = http_result.stdout.strip()
        assert status_code == "200", f"Expected HTTP 200, got {status_code}"


class TestSampleProjectReportsViaWeb:
    """Test sample project compiles and reports are visible via web interface HTTP 200.

    Validates: Requirements 7.6, 9.9 — sample project generates viewable reports
    served through the web interface without additional user action.
    """

    def test_compile_sample_project_success(self, compose_stack: None) -> None:
        """Sample project compiles with zero errors via compile.sh."""
        # Wait for tj-core to be healthy
        assert wait_for_healthy("tj-core", timeout=FULL_STARTUP_TIMEOUT)

        # Clear reports and trigger compilation
        run_docker_exec("tj-core", ["sh", "-c", "rm -rf /app/reports/*"])
        result = run_docker_exec(
            "tj-core",
            ["/app/scripts/compile.sh"],
            timeout=COMPILE_TIMEOUT,
        )
        assert result.returncode == 0, (
            f"Sample project compilation failed:\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )

    def test_reports_served_via_web_http_200(self, compose_stack: None) -> None:
        """After compilation, web interface serves reports with HTTP 200.

        Validates: Requirement 7.6 — reports generated from sample project
        are served through the web interface.
        """
        # Ensure tj-core and tj-web are healthy
        assert wait_for_healthy("tj-core", timeout=FULL_STARTUP_TIMEOUT)
        assert wait_for_healthy("tj-web", timeout=FULL_STARTUP_TIMEOUT)

        # Compile the project to generate reports
        compile_result = run_docker_exec(
            "tj-core",
            ["/app/scripts/compile.sh"],
            timeout=COMPILE_TIMEOUT,
        )
        assert compile_result.returncode == 0, (
            f"Compilation failed: {compile_result.stderr}"
        )

        # Give the web service time to detect new reports
        time.sleep(3)

        # Verify web interface returns HTTP 200
        http_result = run_docker_exec(
            "tj-web",
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:8080/"],
            timeout=HTTP_TIMEOUT,
        )
        assert http_result.returncode == 0, f"curl failed: {http_result.stderr}"
        status_code = http_result.stdout.strip()
        assert status_code == "200", (
            f"Expected HTTP 200 for reports page, got {status_code}"
        )

    def test_html_reports_exist_after_compilation(self, compose_stack: None) -> None:
        """HTML report files are generated and accessible from the web container."""
        # Ensure compilation has run
        assert wait_for_healthy("tj-core", timeout=FULL_STARTUP_TIMEOUT)
        run_docker_exec("tj-core", ["/app/scripts/compile.sh"], timeout=COMPILE_TIMEOUT)

        # Verify HTML reports are visible from tj-web
        result = run_docker_exec(
            "tj-web",
            ["sh", "-c", "find /app/reports -name '*.html' -type f | wc -l"],
        )
        assert result.returncode == 0
        html_count = int(result.stdout.strip())
        assert html_count >= 4, (
            f"Expected at least 4 HTML reports visible from web container, found {html_count}"
        )


class TestTimesheetWorkflow:
    """Test full timesheet workflow: email → processed → included in next compilation.

    Validates: Requirements 7.6, 9.9 — timesheet submission via email is processed
    and incorporated into the next project compilation cycle.
    """

    def test_email_timesheet_processed_and_compiled(self, compose_stack: None) -> None:
        """A timesheet submitted via email is stored and included in next compilation.

        Full workflow:
        1. Send email with .tji attachment to mail service
        2. Verify attachment is stored in timesheets volume
        3. Trigger project compilation
        4. Verify compilation succeeds (timesheet is syntactically valid)
        """
        # Wait for services to be ready
        assert wait_for_healthy("tj-mail", timeout=FULL_STARTUP_TIMEOUT)
        assert wait_for_healthy("tj-core", timeout=FULL_STARTUP_TIMEOUT)

        # Clean up any previous test timesheet
        test_filename = "2024-W05-e2e-test.tji"
        run_docker_exec(
            "tj-mail",
            ["sh", "-c", f"rm -f /app/timesheets/{test_filename}"],
        )

        # Step 1: Send email with valid .tji attachment
        tji_content = (
            b'timesheet e2e_test 2024-01-29 +1w {\n'
            b'  task acme_web.dev.backend.schema {\n'
            b'    work 24h\n'
            b'    status green "E2E test timesheet"\n'
            b'  }\n'
            b'}\n'
        )

        success = send_email_to_mail_container(
            sender="alice@example.com",
            recipient=f"timesheets@{MAIL_DOMAIN}",
            subject="E2E Test Timesheet Week 5",
            body="End-to-end test timesheet submission.",
            attachments=[(test_filename, tji_content)],
        )
        assert success, "Failed to send email to mail container"

        # Step 2: Wait for the email to be processed and file stored
        deadline = time.time() + EMAIL_PROCESS_TIMEOUT
        file_found = False
        while time.time() < deadline:
            result = run_docker_exec(
                "tj-mail",
                ["test", "-f", f"/app/timesheets/{test_filename}"],
            )
            if result.returncode == 0:
                file_found = True
                break
            time.sleep(2)

        assert file_found, (
            f"Timesheet '{test_filename}' was not stored in timesheets volume "
            f"within {EMAIL_PROCESS_TIMEOUT} seconds"
        )

        # Step 3: Trigger project compilation (which includes timesheets)
        compile_result = run_docker_exec(
            "tj-core",
            ["/app/scripts/compile.sh"],
            timeout=COMPILE_TIMEOUT,
        )

        # Step 4: Verify compilation succeeds
        assert compile_result.returncode == 0, (
            f"Compilation failed after timesheet submission:\n"
            f"STDOUT: {compile_result.stdout}\nSTDERR: {compile_result.stderr}"
        )

        # Cleanup
        run_docker_exec(
            "tj-mail",
            ["sh", "-c", f"rm -f /app/timesheets/{test_filename}"],
        )


class TestManualTriggerScripts:
    """Test manual trigger scripts execute successfully against running stack.

    Validates: Requirements 10.1, 10.2, 10.3 — manual trigger scripts for
    rebuild, timesheet collection, and reminders work against a running stack.
    """

    def test_rebuild_script_succeeds(self, compose_stack: None) -> None:
        """scripts/rebuild.sh executes successfully against the running stack.

        Validates: Requirement 10.1 — rebuild.sh triggers project compilation.
        """
        assert wait_for_healthy("tj-core", timeout=FULL_STARTUP_TIMEOUT)

        script_path = SCRIPTS_DIR / "rebuild.sh"
        result = subprocess.run(
            ["bash", str(script_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"rebuild.sh failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        # Verify success indicator in output
        assert "✓" in result.stdout or "completed" in result.stdout.lower(), (
            f"Expected success indicator in output: {result.stdout}"
        )

    def test_collect_timesheets_script_succeeds(self, compose_stack: None) -> None:
        """scripts/collect-timesheets.sh executes successfully against the running stack.

        Validates: Requirement 10.2 — collect-timesheets.sh triggers timesheet collection.
        """
        assert wait_for_healthy("tj-mail", timeout=FULL_STARTUP_TIMEOUT)

        script_path = SCRIPTS_DIR / "collect-timesheets.sh"
        result = subprocess.run(
            ["bash", str(script_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"collect-timesheets.sh failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        assert "✓" in result.stdout or "completed" in result.stdout.lower(), (
            f"Expected success indicator in output: {result.stdout}"
        )

    def test_send_reminders_script_succeeds(self, compose_stack: None) -> None:
        """scripts/send-reminders.sh executes successfully against the running stack.

        Validates: Requirement 10.3 — send-reminders.sh triggers reminder emails.
        """
        assert wait_for_healthy("tj-mail", timeout=FULL_STARTUP_TIMEOUT)

        script_path = SCRIPTS_DIR / "send-reminders.sh"
        result = subprocess.run(
            ["bash", str(script_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"send-reminders.sh failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\nSTDERR: {result.stderr}"
        )
        assert "✓" in result.stdout or "completed" in result.stdout.lower(), (
            f"Expected success indicator in output: {result.stdout}"
        )

    def test_scripts_work_without_cron_service(self, compose_stack: None) -> None:
        """Manual trigger scripts work even when tj-cron is stopped.

        Validates: Requirements 10.1, 10.2, 10.3 — scripts are independent
        of the cron service and only require the target container running.
        """
        # Stop the cron service
        run_compose(["stop", "tj-cron"], timeout=30)

        # Verify tj-core and tj-mail are still healthy
        assert wait_for_healthy("tj-core", timeout=30)
        assert wait_for_healthy("tj-mail", timeout=30)

        # rebuild.sh should still work (targets tj-core, not tj-cron)
        rebuild_result = subprocess.run(
            ["bash", str(SCRIPTS_DIR / "rebuild.sh")],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
        assert rebuild_result.returncode == 0, (
            f"rebuild.sh failed without cron service:\n"
            f"STDOUT: {rebuild_result.stdout}\nSTDERR: {rebuild_result.stderr}"
        )

        # collect-timesheets.sh should still work (targets tj-mail, not tj-cron)
        collect_result = subprocess.run(
            ["bash", str(SCRIPTS_DIR / "collect-timesheets.sh")],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(REPO_ROOT),
        )
        assert collect_result.returncode == 0, (
            f"collect-timesheets.sh failed without cron service:\n"
            f"STDOUT: {collect_result.stdout}\nSTDERR: {collect_result.stderr}"
        )

        # Restart cron service for subsequent tests
        run_compose(["start", "tj-cron"], timeout=30)
