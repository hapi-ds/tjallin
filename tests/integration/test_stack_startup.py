"""Integration tests for Docker Compose stack startup and volume sharing.

These tests validate that the full Docker Compose stack starts correctly,
services reach healthy state, volumes are shared between containers, the
compilation pipeline works end-to-end, and the web service serves reports.

Requires Docker and Docker Compose available in the test environment.
Run with: uv run pytest tests/integration/test_stack_startup.py --tb=short -q -m integration

Requirements: 1.6, 3.5, 4.3, 7.2
"""

import subprocess
import time
from pathlib import Path

import pytest

# Root of the repository (where docker-compose.yml lives)
REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

# Timeout constants
STARTUP_TIMEOUT = 60  # seconds for all services to become healthy
COMPILE_TIMEOUT = 30  # seconds for compilation to complete
HTTP_TIMEOUT = 10  # seconds for HTTP response


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
        # If startup fails, still try to capture logs for debugging
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


class TestServiceHealth:
    """Test that all services reach healthy state within the timeout.

    Validates: Requirement 1.6 — all four services running within 60 seconds.
    """

    def test_tj_core_healthy(self, compose_stack: None) -> None:
        """TJ Core service reaches healthy state within 60 seconds."""
        assert wait_for_healthy("tj-core", timeout=STARTUP_TIMEOUT), (
            "tj-core did not reach healthy state within 60 seconds"
        )

    def test_tj_web_healthy(self, compose_stack: None) -> None:
        """TJ Web service reaches healthy state within 60 seconds."""
        assert wait_for_healthy("tj-web", timeout=STARTUP_TIMEOUT), (
            "tj-web did not reach healthy state within 60 seconds"
        )

    def test_tj_mail_healthy(self, compose_stack: None) -> None:
        """TJ Mail service reaches healthy state within 60 seconds."""
        assert wait_for_healthy("tj-mail", timeout=STARTUP_TIMEOUT), (
            "tj-mail did not reach healthy state within 60 seconds"
        )

    def test_tj_cron_healthy(self, compose_stack: None) -> None:
        """TJ Cron service reaches healthy state within 60 seconds."""
        assert wait_for_healthy("tj-cron", timeout=STARTUP_TIMEOUT), (
            "tj-cron did not reach healthy state within 60 seconds"
        )


class TestVolumeSharing:
    """Test that volumes are correctly shared between containers.

    Validates: Requirement 3.5 — reports available to web service via shared volume.
    """

    def test_write_in_core_read_in_web(self, compose_stack: None) -> None:
        """A file written in tj-core's report volume is readable from tj-web."""
        test_filename = "test_volume_share.txt"
        test_content = "volume-sharing-works"

        # Write a file in tj-core's report directory
        write_result = run_docker_exec(
            "tj-core",
            ["sh", "-c", f"echo '{test_content}' > /app/reports/{test_filename}"],
        )
        assert write_result.returncode == 0, (
            f"Failed to write file in tj-core: {write_result.stderr}"
        )

        # Read the same file from tj-web's report directory (mounted read-only)
        read_result = run_docker_exec(
            "tj-web",
            ["cat", f"/app/reports/{test_filename}"],
        )
        assert read_result.returncode == 0, (
            f"Failed to read file in tj-web: {read_result.stderr}"
        )
        assert test_content in read_result.stdout.strip(), (
            f"Content mismatch: expected '{test_content}', got '{read_result.stdout.strip()}'"
        )

        # Cleanup
        run_docker_exec("tj-core", ["rm", f"/app/reports/{test_filename}"])

    def test_project_volume_shared(self, compose_stack: None) -> None:
        """The project volume is accessible from both tj-core and tj-web."""
        # The project.tjp file should be visible in both containers
        core_result = run_docker_exec(
            "tj-core",
            ["test", "-f", "/app/project/project.tjp"],
        )
        assert core_result.returncode == 0, "project.tjp not found in tj-core"

        web_result = run_docker_exec(
            "tj-web",
            ["test", "-f", "/app/project/project.tjp"],
        )
        assert web_result.returncode == 0, "project.tjp not found in tj-web"


class TestCompilationPipeline:
    """Test the compilation pipeline: place .tjp file, compile, verify reports.

    Validates: Requirement 3.5 — generated reports replace previous reports.
    """

    def test_compile_produces_reports(self, compose_stack: None) -> None:
        """Triggering compilation generates report files in the report volume."""
        # Clear any existing reports
        run_docker_exec("tj-core", ["sh", "-c", "rm -rf /app/reports/*"])

        # Trigger compilation via the compile script
        compile_result = run_docker_exec(
            "tj-core",
            ["/app/scripts/compile.sh"],
            timeout=COMPILE_TIMEOUT,
        )
        assert compile_result.returncode == 0, (
            f"Compilation failed:\nSTDOUT: {compile_result.stdout}\nSTDERR: {compile_result.stderr}"
        )

        # Verify reports were generated
        list_result = run_docker_exec(
            "tj-core",
            ["sh", "-c", "find /app/reports -type f | wc -l"],
        )
        report_count = int(list_result.stdout.strip())
        assert report_count > 0, "No reports generated after compilation"

    def test_compile_generates_html_reports(self, compose_stack: None) -> None:
        """Compilation generates HTML report files."""
        # Trigger compilation
        compile_result = run_docker_exec(
            "tj-core",
            ["/app/scripts/compile.sh"],
            timeout=COMPILE_TIMEOUT,
        )
        assert compile_result.returncode == 0, (
            f"Compilation failed: {compile_result.stderr}"
        )

        # Check for HTML files in reports
        html_result = run_docker_exec(
            "tj-core",
            ["sh", "-c", "find /app/reports -name '*.html' | wc -l"],
        )
        html_count = int(html_result.stdout.strip())
        assert html_count > 0, "No HTML reports generated"

    def test_reports_visible_from_web_container(self, compose_stack: None) -> None:
        """Reports generated by tj-core are visible in tj-web's report volume."""
        # Compile first
        run_docker_exec("tj-core", ["/app/scripts/compile.sh"], timeout=COMPILE_TIMEOUT)

        # Check reports are visible from tj-web
        web_result = run_docker_exec(
            "tj-web",
            ["sh", "-c", "find /app/reports -type f -name '*.html' | head -1"],
        )
        assert web_result.returncode == 0
        assert web_result.stdout.strip() != "", (
            "No HTML reports visible from tj-web container"
        )


class TestWebServing:
    """Test that the web service serves compiled reports via HTTP.

    Validates: Requirements 4.3, 7.2 — web interface returns HTTP 200.
    """

    def test_web_returns_200(self, compose_stack: None) -> None:
        """Web service returns HTTP 200 after reports are compiled."""
        # Ensure reports exist by triggering compilation
        compile_result = run_docker_exec(
            "tj-core",
            ["/app/scripts/compile.sh"],
            timeout=COMPILE_TIMEOUT,
        )
        assert compile_result.returncode == 0, (
            f"Compilation failed: {compile_result.stderr}"
        )

        # Give the web service a moment to detect new reports
        time.sleep(3)

        # Use curl from inside the tj-web container to check HTTP response
        http_result = run_docker_exec(
            "tj-web",
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:8080/"],
            timeout=HTTP_TIMEOUT,
        )
        assert http_result.returncode == 0, (
            f"curl failed: {http_result.stderr}"
        )
        status_code = http_result.stdout.strip()
        assert status_code == "200", (
            f"Expected HTTP 200, got {status_code}"
        )

    def test_fallback_page_when_no_reports(self, compose_stack: None) -> None:
        """Web service serves a fallback page when no reports exist."""
        # Clear all reports
        run_docker_exec("tj-core", ["sh", "-c", "rm -rf /app/reports/*"])

        # Give the web service time to detect the change
        time.sleep(5)

        # The web service should still respond (either with fallback or normal page)
        http_result = run_docker_exec(
            "tj-web",
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://localhost:8080/"],
            timeout=HTTP_TIMEOUT,
        )
        assert http_result.returncode == 0, (
            f"curl failed: {http_result.stderr}"
        )
        # Should still return 200 (serving fallback page)
        status_code = http_result.stdout.strip()
        assert status_code == "200", (
            f"Expected HTTP 200 for fallback page, got {status_code}"
        )
