"""Integration tests for mail service startup without external relay configuration.

These tests validate that the mail service starts and accepts SMTP/IMAP
connections without TJ_SMTP_RELAY_HOST and TJ_SMTP_RELAY_PORT environment
variables, confirming the stack is fully self-contained.

Requires Docker and Docker Compose available in the test environment.
Run with: uv run pytest tests/integration/test_startup_no_relay.py --tb=short -q -m integration

Requirements: 4.1, 4.2
"""

import subprocess
import time
from pathlib import Path

import pytest

# Root of the repository (where docker-compose.yml lives)
REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

# Timeout constants
STARTUP_TIMEOUT = 60  # seconds for service to accept connections (Requirement 4.2)
CONNECT_TIMEOUT = 10  # seconds for individual connection attempts


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


def run_compose(
    args: list[str], timeout: int = 60, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a docker compose command in the repo root.

    Args:
        args: Arguments to pass after 'docker compose'.
        timeout: Command timeout in seconds.
        env: Optional environment variable overrides.

    Returns:
        CompletedProcess with stdout/stderr captured.
    """
    import os

    cmd = ["docker", "compose", "-f", str(COMPOSE_FILE)] + args
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(REPO_ROOT),
        env=run_env,
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


def wait_for_smtp_accepting(timeout: int = STARTUP_TIMEOUT) -> bool:
    """Wait for the SMTP server inside tj-mail to accept connections.

    Uses nc (netcat) inside the container to test port 25 connectivity.

    Args:
        timeout: Maximum seconds to wait.

    Returns:
        True if SMTP is accepting connections within timeout, False otherwise.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = run_docker_exec(
            "tj-mail",
            ["sh", "-c", "echo QUIT | nc -w 2 localhost 25"],
            timeout=CONNECT_TIMEOUT,
        )
        if result.returncode == 0 and "220" in result.stdout:
            return True
        time.sleep(2)
    return False


def wait_for_imap_accepting(timeout: int = STARTUP_TIMEOUT) -> bool:
    """Wait for the IMAP server inside tj-mail to accept connections.

    Uses nc (netcat) inside the container to test port 143 connectivity.

    Args:
        timeout: Maximum seconds to wait.

    Returns:
        True if IMAP is accepting connections within timeout, False otherwise.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = run_docker_exec(
            "tj-mail",
            ["sh", "-c", "echo 'a001 LOGOUT' | nc -w 2 localhost 143"],
            timeout=CONNECT_TIMEOUT,
        )
        if result.returncode == 0 and ("OK" in result.stdout or "IMAP" in result.stdout):
            return True
        time.sleep(2)
    return False


@pytest.fixture(scope="module")
def compose_stack_no_relay():
    """Start the Docker Compose stack without relay variables.

    Ensures TJ_SMTP_RELAY_HOST and TJ_SMTP_RELAY_PORT are explicitly unset
    so the mail service starts in local-only delivery mode.

    Tears down the stack (including volumes) after all tests complete.
    """
    # Explicitly unset relay variables to test local-only mode
    env_overrides = {
        "TJ_SMTP_RELAY_HOST": "",
        "TJ_SMTP_RELAY_PORT": "",
    }

    # Start only the tj-mail service (and its dependencies) to isolate the test
    result = run_compose(
        ["up", "-d", "--build", "tj-mail"],
        timeout=300,
        env=env_overrides,
    )
    if result.returncode != 0:
        logs = run_compose(["logs", "tj-mail", "--tail=50"], timeout=30)
        pytest.fail(
            f"docker compose up tj-mail failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}\n"
            f"LOGS: {logs.stdout}"
        )

    yield

    # Tear down: stop containers and remove volumes
    run_compose(["down", "-v", "--timeout", "10"], timeout=60)


class TestStartupWithoutRelay:
    """Test that the mail service starts without external relay configuration.

    Validates: Requirements 4.1, 4.2
    - 4.1: Mail service sends outbound emails via local SMTP without requiring
            TJ_SMTP_HOST, TJ_SMTP_PORT, TJ_SMTP_USER, or TJ_SMTP_PASSWORD.
    - 4.2: Mail service starts and accepts SMTP connections within 30 seconds
            without relay environment variables.
    """

    def test_mail_service_starts_without_relay(
        self, compose_stack_no_relay: None
    ) -> None:
        """Mail service reaches healthy state without relay variables.

        Validates Requirement 4.2: the service starts without
        TJ_SMTP_RELAY_HOST and TJ_SMTP_RELAY_PORT.
        """
        healthy = wait_for_healthy("tj-mail", timeout=STARTUP_TIMEOUT)
        assert healthy, (
            "tj-mail did not reach healthy state within "
            f"{STARTUP_TIMEOUT}s without relay variables"
        )

    def test_smtp_accepts_connections_within_30s(
        self, compose_stack_no_relay: None
    ) -> None:
        """SMTP server accepts connections within 30 seconds of startup.

        Validates Requirement 4.2: the SMTP server begins accepting
        connections within 30 seconds when started without relay config.
        """
        accepting = wait_for_smtp_accepting(timeout=30)
        assert accepting, (
            "SMTP server did not accept connections within 30 seconds "
            "of startup (without relay variables)"
        )

    def test_imap_accepts_connections_within_30s(
        self, compose_stack_no_relay: None
    ) -> None:
        """IMAP server accepts connections within 30 seconds of startup.

        Validates Requirement 4.2 (SMTP) and 2.7 (IMAP startup):
        both services should be ready within 30 seconds.
        """
        accepting = wait_for_imap_accepting(timeout=30)
        assert accepting, (
            "IMAP server did not accept connections within 30 seconds "
            "of startup (without relay variables)"
        )

    def test_smtp_delivers_locally_without_relay(
        self, compose_stack_no_relay: None
    ) -> None:
        """SMTP delivers messages to local Maildir without relay.

        Validates Requirement 4.1: the mail service delivers messages
        via the local SMTP server without external relay credentials.
        """
        # Wait for SMTP to be ready
        assert wait_for_smtp_accepting(timeout=30), "SMTP not ready"

        # Send a test message to a local user
        raw_email = (
            "From: sender@taskjuggler.local\r\n"
            "To: alice@taskjuggler.local\r\n"
            "Subject: no-relay-delivery-test\r\n"
            "Date: Mon, 01 Jan 2024 12:00:00 +0000\r\n"
            "\r\n"
            "This message was delivered without an external relay.\r\n"
        )

        cmd = [
            "docker", "compose", "-f", str(COMPOSE_FILE),
            "exec", "-T", "tj-mail",
            "sendmail", "-f", "sender@taskjuggler.local", "alice@taskjuggler.local",
        ]
        result = subprocess.run(
            cmd,
            input=raw_email,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"sendmail failed: {result.stderr}"
        )

        # Wait for the message to appear in alice's Maildir
        deadline = time.time() + 30
        found = False
        while time.time() < deadline:
            check = run_docker_exec(
                "tj-mail",
                [
                    "sh", "-c",
                    "grep -rl 'no-relay-delivery-test' /var/mail/alice/Maildir/ 2>/dev/null",
                ],
            )
            if check.returncode == 0 and check.stdout.strip():
                found = True
                break
            time.sleep(2)

        assert found, (
            "Message was not delivered to local Maildir without relay — "
            "local-only delivery mode may not be working"
        )

    def test_no_relay_env_vars_in_container(
        self, compose_stack_no_relay: None
    ) -> None:
        """Verify relay environment variables are not set inside the container.

        Confirms the test environment correctly excludes relay configuration.
        """
        # Check that TJ_SMTP_RELAY_HOST is empty or unset
        result = run_docker_exec(
            "tj-mail",
            ["sh", "-c", "echo \"RELAY=${TJ_SMTP_RELAY_HOST:-unset}\""],
        )
        relay_value = result.stdout.strip()
        assert "unset" in relay_value or relay_value == "RELAY=", (
            f"TJ_SMTP_RELAY_HOST should be unset, got: {relay_value}"
        )
