"""Shared fixtures for Docker-based integration tests.

These fixtures provide connection details and helpers for testing the
mail service (SMTP and IMAP) against a running Docker Compose stack.

Run with: uv run pytest tests/integration/ --tb=short -q -m integration
"""

import os
import smtplib
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

# Root of the repository (where docker-compose.yml lives)
REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"


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


def mail_service_running() -> bool:
    """Check if the tj-mail service is running and healthy."""
    try:
        result = subprocess.run(
            [
                "docker", "compose", "-f", str(COMPOSE_FILE),
                "ps", "--format", "{{.Health}}", "--filter", "service=tj-mail",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(REPO_ROOT),
        )
        return result.returncode == 0 and "healthy" in result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


@dataclass
class MailConfig:
    """Connection configuration for the mail service."""

    smtp_host: str
    smtp_port: int
    imap_host: str
    imap_port: int
    domain: str
    users: dict[str, str]  # username -> password


@pytest.fixture(scope="session")
def mail_config() -> MailConfig:
    """Provide mail service connection configuration from environment or defaults.

    Returns:
        MailConfig with connection details for SMTP and IMAP.
    """
    smtp_host = os.environ.get("TJ_TEST_SMTP_HOST", "localhost")
    smtp_port = int(os.environ.get("TJ_TEST_SMTP_PORT", "25"))
    imap_host = os.environ.get("TJ_TEST_IMAP_HOST", "localhost")
    imap_port = int(os.environ.get("TJ_TEST_IMAP_PORT", "1143"))
    domain = os.environ.get("TJ_MAIL_DOMAIN", "taskjuggler.local")

    # Parse users from TJ_MAIL_USERS or use defaults
    mail_users_str = os.environ.get("TJ_MAIL_USERS", "alice:secret1,bob:secret2")
    users: dict[str, str] = {}
    for entry in mail_users_str.split(","):
        if ":" in entry:
            username, password = entry.split(":", 1)
            users[username.strip()] = password.strip()

    return MailConfig(
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        imap_host=imap_host,
        imap_port=imap_port,
        domain=domain,
        users=users,
    )


@pytest.fixture(scope="session")
def smtp_connection(mail_config: MailConfig) -> smtplib.SMTP:
    """Create and return an SMTP connection to the mail service.

    Returns:
        Connected SMTP client.
    """
    smtp = smtplib.SMTP(mail_config.smtp_host, mail_config.smtp_port, timeout=10)
    yield smtp
    smtp.quit()


def wait_for_smtp(host: str, port: int, timeout: int = 30) -> bool:
    """Wait for the SMTP server to accept connections.

    Args:
        host: SMTP server hostname.
        port: SMTP server port.
        timeout: Maximum seconds to wait.

    Returns:
        True if connection succeeded within timeout.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with smtplib.SMTP(host, port, timeout=5) as smtp:
                smtp.noop()
                return True
        except (ConnectionRefusedError, OSError, smtplib.SMTPException):
            time.sleep(1)
    return False
