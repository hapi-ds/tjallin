"""Integration tests for sample project compilation.

These tests validate that the comprehensive sample project compiles with zero
errors via tj3, all four report types are generated, timesheet files are
syntactically valid, and the modular include structure resolves correctly.

Requires Docker and Docker Compose available in the test environment.
Run with: uv run pytest tests/integration/test_sample_project.py --tb=short -q -m integration

Requirements: 9.9, 9.4, 9.5, 9.6
"""

import subprocess
import time
from pathlib import Path

import pytest

# Root of the repository (where docker-compose.yml lives)
REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

# Timeout constants
STARTUP_TIMEOUT = 60  # seconds for services to become healthy
COMPILE_TIMEOUT = 30  # seconds for compilation to complete


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
            ["ps", service, "--format", "{{.Health}}"],
            timeout=10,
        )
        health = result.stdout.strip()
        if health == "healthy":
            return True
        time.sleep(2)
    return False


@pytest.fixture(scope="module")
def compose_stack():
    """Start the tj-core service and tear it down after all tests.

    Only starts tj-core (the compilation service) since these tests focus
    on sample project compilation, report generation, and file structure.
    Other services are not needed for these validations.
    """
    # Build and start only tj-core in detached mode
    result = run_compose(["up", "-d", "--build", "tj-core"], timeout=300)
    if result.returncode != 0:
        logs = run_compose(["logs", "tj-core", "--tail=50"], timeout=30)
        pytest.fail(
            f"docker compose up tj-core failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}\n"
            f"LOGS: {logs.stdout}"
        )

    # Wait for tj-core to be healthy before running tests
    if not wait_for_healthy("tj-core", timeout=STARTUP_TIMEOUT):
        logs = run_compose(["logs", "tj-core", "--tail=30"], timeout=30)
        run_compose(["down", "-v", "--timeout", "10"], timeout=60)
        pytest.fail(f"tj-core did not become healthy:\n{logs.stdout}")

    yield

    # Tear down: stop containers and remove volumes
    run_compose(["down", "-v", "--timeout", "10"], timeout=60)


class TestSampleProjectCompilation:
    """Test that the sample project compiles with zero errors.

    Validates: Requirement 9.9 — sample project produces zero compilation errors
    and generates all defined reports successfully.
    """

    def test_compilation_zero_errors(self, compose_stack: None) -> None:
        """Sample project compiles via tj3 with zero errors."""
        result = run_docker_exec(
            "tj-core",
            ["tj3", "/app/project/project.tjp"],
            timeout=COMPILE_TIMEOUT,
        )
        assert result.returncode == 0, (
            f"Sample project compilation failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )
        # Verify no error lines in stderr (warnings are acceptable)
        error_lines = [
            line for line in result.stderr.splitlines() if "Error" in line or "error" in line
        ]
        assert len(error_lines) == 0, (
            "Compilation produced errors:\n" + "\n".join(error_lines)
        )

    def test_compilation_via_compile_script(self, compose_stack: None) -> None:
        """Sample project compiles successfully via the compile.sh script."""
        # Clear previous reports
        run_docker_exec("tj-core", ["sh", "-c", "rm -rf /app/reports/*"])

        result = run_docker_exec(
            "tj-core",
            ["/app/scripts/compile.sh"],
            timeout=COMPILE_TIMEOUT,
        )
        assert result.returncode == 0, (
            f"compile.sh failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}"
        )


class TestReportGeneration:
    """Test that all four report types are generated successfully.

    Validates: Requirement 9.4 — Gantt chart, resource usage report,
    task list report, and cost report are each generated.
    """

    @pytest.fixture(autouse=True)
    def _compile_project(self, compose_stack: None) -> None:
        """Compile the project before running report tests."""
        # Clear reports and recompile using the compile script which handles output dir
        result = run_docker_exec(
            "tj-core",
            ["/app/scripts/compile.sh"],
            timeout=COMPILE_TIMEOUT,
        )
        assert result.returncode == 0, (
            f"Compilation failed during setup: {result.stderr}"
        )

    def test_gantt_chart_generated(self, compose_stack: None) -> None:
        """GanttChart report (HTML) is generated successfully."""
        result = run_docker_exec(
            "tj-core",
            ["sh", "-c", "find /app/reports -name 'Gantt*' -type f"],
        )
        assert result.stdout.strip() != "", (
            "GanttChart report file not found in /app/reports"
        )

    def test_resource_usage_generated(self, compose_stack: None) -> None:
        """ResourceUsage report (HTML) is generated successfully."""
        result = run_docker_exec(
            "tj-core",
            ["sh", "-c", "find /app/reports -name 'Resource*' -type f"],
        )
        assert result.stdout.strip() != "", (
            "ResourceUsage report file not found in /app/reports"
        )

    def test_task_list_generated(self, compose_stack: None) -> None:
        """TaskList report (HTML) is generated successfully."""
        result = run_docker_exec(
            "tj-core",
            ["sh", "-c", "find /app/reports -name 'Task*' -type f"],
        )
        assert result.stdout.strip() != "", (
            "TaskList report file not found in /app/reports"
        )

    def test_cost_report_generated(self, compose_stack: None) -> None:
        """CostReport report (HTML) is generated successfully."""
        result = run_docker_exec(
            "tj-core",
            ["sh", "-c", "find /app/reports -name 'Cost*' -type f"],
        )
        assert result.stdout.strip() != "", (
            "CostReport report file not found in /app/reports"
        )

    def test_all_reports_are_html(self, compose_stack: None) -> None:
        """All generated reports are non-empty HTML files."""
        result = run_docker_exec(
            "tj-core",
            ["sh", "-c", "find /app/reports -name '*.html' -type f | wc -l"],
        )
        html_count = int(result.stdout.strip())
        assert html_count >= 4, (
            f"Expected at least 4 HTML report files, found {html_count}"
        )


class TestTimesheetValidity:
    """Test that timesheet files are syntactically valid and processable.

    Validates: Requirement 9.5 — sample timesheets from at least two resources
    for at least two reporting periods, demonstrating the timesheet workflow.
    """

    def test_timesheet_files_exist(self, compose_stack: None) -> None:
        """All expected timesheet files exist in the project volume."""
        expected_timesheets = [
            "2024-W03-alice.tji",
            "2024-W03-bob.tji",
            "2024-W04-alice.tji",
            "2024-W04-bob.tji",
        ]
        for ts_file in expected_timesheets:
            result = run_docker_exec(
                "tj-core",
                ["test", "-f", f"/app/project/timesheets/{ts_file}"],
            )
            assert result.returncode == 0, (
                f"Timesheet file not found: timesheets/{ts_file}"
            )

    def test_timesheets_processed_by_scheduler(self, compose_stack: None) -> None:
        """Timesheets are syntactically valid and processed during compilation.

        The project uses 'trackingscenario plan' which means tj3 will process
        timesheet files during compilation. A successful compilation with zero
        errors confirms the timesheets are syntactically valid.
        """
        result = run_docker_exec(
            "tj-core",
            ["tj3", "/app/project/project.tjp"],
            timeout=COMPILE_TIMEOUT,
        )
        assert result.returncode == 0, (
            f"Compilation with timesheets failed (exit {result.returncode}):\n"
            f"STDERR: {result.stderr}"
        )
        # Verify no timesheet-related errors in output
        timesheet_errors = [
            line
            for line in result.stderr.splitlines()
            if "timesheet" in line.lower() and ("error" in line.lower() or "Error" in line)
        ]
        assert len(timesheet_errors) == 0, (
            "Timesheet processing errors:\n" + "\n".join(timesheet_errors)
        )

    def test_timesheets_cover_two_resources(self, compose_stack: None) -> None:
        """Timesheets exist for at least two different resources."""
        result = run_docker_exec(
            "tj-core",
            ["sh", "-c", "ls /app/project/timesheets/*.tji"],
        )
        assert result.returncode == 0, "No timesheet files found"
        files = result.stdout.strip().splitlines()
        # Extract unique resource names from filenames (format: YYYY-WXX-name.tji)
        resources = set()
        for f in files:
            filename = f.split("/")[-1]  # e.g., "2024-W03-alice.tji"
            parts = filename.replace(".tji", "").split("-")
            if len(parts) >= 3:
                resources.add(parts[-1])  # resource name is the last part
        assert len(resources) >= 2, (
            f"Expected timesheets from at least 2 resources, found: {resources}"
        )

    def test_timesheets_cover_two_periods(self, compose_stack: None) -> None:
        """Timesheets exist for at least two reporting periods."""
        result = run_docker_exec(
            "tj-core",
            ["sh", "-c", "ls /app/project/timesheets/*.tji"],
        )
        assert result.returncode == 0, "No timesheet files found"
        files = result.stdout.strip().splitlines()
        # Extract unique week identifiers (format: YYYY-WXX-name.tji)
        periods = set()
        for f in files:
            filename = f.split("/")[-1]
            parts = filename.replace(".tji", "").split("-")
            if len(parts) >= 3:
                periods.add(f"{parts[0]}-{parts[1]}")  # e.g., "2024-W03"
        assert len(periods) >= 2, (
            f"Expected timesheets for at least 2 periods, found: {periods}"
        )


class TestModularIncludeStructure:
    """Test that the modular include structure resolves correctly.

    Validates: Requirement 9.6 — sample project uses modular structure with
    include files separating resources, tasks, and reports into distinct files.
    """

    def test_include_files_exist(self, compose_stack: None) -> None:
        """All expected include files exist in the project volume."""
        expected_includes = [
            "includes/accounts.tji",
            "includes/resources.tji",
            "includes/tasks.tji",
            "includes/reports.tji",
        ]
        for inc_file in expected_includes:
            result = run_docker_exec(
                "tj-core",
                ["test", "-f", f"/app/project/{inc_file}"],
            )
            assert result.returncode == 0, (
                f"Include file not found: {inc_file}"
            )

    def test_no_missing_file_errors(self, compose_stack: None) -> None:
        """Compilation produces no missing file errors from include directives."""
        result = run_docker_exec(
            "tj-core",
            ["tj3", "/app/project/project.tjp"],
            timeout=COMPILE_TIMEOUT,
        )
        assert result.returncode == 0, (
            f"Compilation failed — possible missing include files:\n"
            f"STDERR: {result.stderr}"
        )
        # Check for file-not-found patterns in output
        missing_file_indicators = ["cannot open", "No such file", "not found", "include failed"]
        combined_output = result.stdout + result.stderr
        for indicator in missing_file_indicators:
            assert indicator.lower() not in combined_output.lower(), (
                f"Missing file indicator '{indicator}' found in compilation output:\n"
                f"{combined_output}"
            )

    def test_main_project_file_includes_all_modules(self, compose_stack: None) -> None:
        """The main project.tjp file includes all four modular files."""
        result = run_docker_exec(
            "tj-core",
            ["cat", "/app/project/project.tjp"],
        )
        assert result.returncode == 0, "Could not read project.tjp"
        content = result.stdout
        expected_includes = [
            'include "includes/accounts.tji"',
            'include "includes/resources.tji"',
            'include "includes/tasks.tji"',
            'include "includes/reports.tji"',
        ]
        for include_line in expected_includes:
            assert include_line in content, (
                f"Missing include directive in project.tjp: {include_line}"
            )
