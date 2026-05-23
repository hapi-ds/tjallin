"""Integration tests for report navigation headers after compilation.

These tests validate the full report pipeline: TJ3 compilation →
post-processing → navigation headers injected into HTML reports.
Verifies that all reports contain cross-linked navigation, the
JournalReport is included, index.html is generated, and all links
are relative.

Requires Docker and Docker Compose available in the test environment.
Run with: uv run pytest tests/integration/test_report_navigation.py --tb=short -q -m integration

Requirements: 5.1, 5.4, 5.5, 6.5
"""

from __future__ import annotations

import re
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
            ["ps", "--format", "{{.Health}}", "--filter", f"service={service}"],
            timeout=10,
        )
        health = result.stdout.strip()
        if health == "healthy":
            return True
        time.sleep(2)
    return False


@pytest.fixture(scope="module")
def compiled_reports() -> dict[str, str]:
    """Start the stack, compile the project, and return report HTML contents.

    Builds and starts the Docker Compose stack, waits for tj-core to be
    healthy, triggers compilation, then reads all generated HTML report
    files from the report-data volume.

    Returns:
        Dictionary mapping filename → HTML content for each report file.
    """
    # Build and start the stack
    result = run_compose(["up", "-d", "--build"], timeout=300)
    if result.returncode != 0:
        logs = run_compose(["logs", "--tail=50"], timeout=30)
        pytest.fail(
            f"docker compose up failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}\n"
            f"LOGS: {logs.stdout}"
        )

    try:
        # Wait for tj-core to be healthy
        assert wait_for_healthy("tj-core", timeout=STARTUP_TIMEOUT), (
            "tj-core did not reach healthy state"
        )

        # Clear previous reports and trigger compilation
        run_docker_exec("tj-core", ["sh", "-c", "rm -rf /app/reports/*"])
        compile_result = run_docker_exec(
            "tj-core",
            ["/app/scripts/compile.sh"],
            timeout=COMPILE_TIMEOUT,
        )
        assert compile_result.returncode == 0, (
            f"Compilation failed:\nSTDOUT: {compile_result.stdout}\n"
            f"STDERR: {compile_result.stderr}"
        )

        # List all HTML files in the report directory
        list_result = run_docker_exec(
            "tj-core",
            ["sh", "-c", "find /app/reports -name '*.html' -type f"],
        )
        assert list_result.returncode == 0, (
            f"Failed to list reports: {list_result.stderr}"
        )

        html_files = [
            f.strip() for f in list_result.stdout.strip().splitlines() if f.strip()
        ]
        assert len(html_files) > 0, "No HTML reports generated after compilation"

        # Read each HTML file content
        reports: dict[str, str] = {}
        for filepath in html_files:
            filename = filepath.split("/")[-1]
            cat_result = run_docker_exec(
                "tj-core",
                ["cat", filepath],
            )
            if cat_result.returncode == 0:
                reports[filename] = cat_result.stdout

        return reports

    finally:
        # Tear down the stack
        run_compose(["down", "-v", "--timeout", "10"], timeout=60)


# Known reports defined in project/includes/reports.tji
EXPECTED_REPORTS = [
    "GanttChart.html",
    "ResourceUsage.html",
    "TaskList.html",
    "CostReport.html",
    "JournalReport.html",
]


class TestNavigationHeaders:
    """Test that compiled reports contain navigation headers with cross-links.

    Validates: Requirement 5.1 — navigation header in each HTML report
    containing links to all other reports and to the Report_Index.
    """

    def test_reports_contain_nav_header(self, compiled_reports: dict[str, str]) -> None:
        """Each report contains a <nav class="tj-nav-header"> element."""
        for filename, content in compiled_reports.items():
            assert 'class="tj-nav-header"' in content, (
                f"{filename} is missing the navigation header"
            )

    def test_each_report_links_to_all_others(self, compiled_reports: dict[str, str]) -> None:
        """Each report's nav header contains links to every other report.

        Validates: Requirement 5.1, 5.5 — navigation header contains links
        to all other reports in the set.
        """
        # Get all report filenames (excluding index.html)
        report_filenames = [f for f in compiled_reports if f != "index.html"]

        for filename in report_filenames:
            content = compiled_reports[filename]
            # Extract the nav header content
            nav_match = re.search(
                r'<nav class="tj-nav-header">(.*?)</nav>',
                content,
                re.DOTALL,
            )
            assert nav_match is not None, (
                f"{filename} has no nav header to check links in"
            )
            nav_content = nav_match.group(1)

            # Check that every other report is linked
            for other_filename in report_filenames:
                if other_filename == filename:
                    continue
                assert f'href="{other_filename}"' in nav_content, (
                    f"{filename} is missing link to {other_filename}"
                )

    def test_nav_header_links_to_index(self, compiled_reports: dict[str, str]) -> None:
        """Each report's nav header contains a link to index.html.

        Validates: Requirement 5.1 — navigation includes link to Report_Index.
        """
        report_filenames = [f for f in compiled_reports if f != "index.html"]

        for filename in report_filenames:
            content = compiled_reports[filename]
            nav_match = re.search(
                r'<nav class="tj-nav-header">(.*?)</nav>',
                content,
                re.DOTALL,
            )
            assert nav_match is not None, f"{filename} has no nav header"
            nav_content = nav_match.group(1)
            assert 'href="index.html"' in nav_content, (
                f"{filename} is missing link to index.html in nav header"
            )


class TestJournalReportInNavigation:
    """Test that the JournalReport is included in navigation.

    Validates: Requirement 6.5 — Journal report includes cross-link
    navigation header consistent with all other reports.
    """

    def test_journal_report_generated(self, compiled_reports: dict[str, str]) -> None:
        """JournalReport.html is generated as part of compilation."""
        assert "JournalReport.html" in compiled_reports, (
            "JournalReport.html was not generated during compilation"
        )

    def test_journal_report_has_nav_header(self, compiled_reports: dict[str, str]) -> None:
        """JournalReport.html contains the navigation header."""
        assert "JournalReport.html" in compiled_reports
        content = compiled_reports["JournalReport.html"]
        assert 'class="tj-nav-header"' in content, (
            "JournalReport.html is missing the navigation header"
        )

    def test_other_reports_link_to_journal(self, compiled_reports: dict[str, str]) -> None:
        """All other reports include a link to JournalReport.html in their nav."""
        report_filenames = [
            f for f in compiled_reports if f != "index.html" and f != "JournalReport.html"
        ]

        for filename in report_filenames:
            content = compiled_reports[filename]
            nav_match = re.search(
                r'<nav class="tj-nav-header">(.*?)</nav>',
                content,
                re.DOTALL,
            )
            assert nav_match is not None, f"{filename} has no nav header"
            nav_content = nav_match.group(1)
            assert 'href="JournalReport.html"' in nav_content, (
                f"{filename} is missing link to JournalReport.html"
            )


class TestReportIndex:
    """Test that index.html is generated with links to all reports.

    Validates: Requirement 5.4 — Report_Index page listing all reports
    with their titles and links.
    """

    def test_index_html_generated(self, compiled_reports: dict[str, str]) -> None:
        """index.html is generated after compilation."""
        assert "index.html" in compiled_reports, (
            "index.html was not generated during compilation"
        )

    def test_index_contains_links_to_all_reports(
        self, compiled_reports: dict[str, str]
    ) -> None:
        """index.html contains links to every report file."""
        assert "index.html" in compiled_reports
        index_content = compiled_reports["index.html"]

        report_filenames = [f for f in compiled_reports if f != "index.html"]
        for filename in report_filenames:
            assert f'href="{filename}"' in index_content, (
                f"index.html is missing link to {filename}"
            )

    def test_index_contains_report_titles(self, compiled_reports: dict[str, str]) -> None:
        """index.html contains human-readable titles for reports."""
        assert "index.html" in compiled_reports
        index_content = compiled_reports["index.html"]

        # The index should contain recognizable report titles
        # (from the reports.tji definitions)
        expected_titles = [
            "Gantt Chart",
            "Resource Usage",
            "Task List",
            "Cost Report",
            "Project Journal",
        ]
        for title in expected_titles:
            assert title in index_content, (
                f"index.html is missing title '{title}'"
            )

    def test_index_has_nav_header(self, compiled_reports: dict[str, str]) -> None:
        """index.html itself contains the navigation header."""
        assert "index.html" in compiled_reports
        index_content = compiled_reports["index.html"]
        assert 'class="tj-nav-header"' in index_content, (
            "index.html is missing the navigation header"
        )


class TestRelativeLinks:
    """Test that all navigation links use relative paths.

    Validates: Requirement 5.2 — Cross_Link elements use relative file
    paths so reports remain navigable from any directory.
    """

    def test_no_absolute_links_in_nav(self, compiled_reports: dict[str, str]) -> None:
        """Navigation headers contain no absolute paths (no leading /)."""
        for filename, content in compiled_reports.items():
            nav_match = re.search(
                r'<nav class="tj-nav-header">(.*?)</nav>',
                content,
                re.DOTALL,
            )
            if nav_match is None:
                continue
            nav_content = nav_match.group(1)

            # Extract all href values
            hrefs = re.findall(r'href="([^"]*)"', nav_content)
            for href in hrefs:
                assert not href.startswith("/"), (
                    f"{filename}: nav link '{href}' uses absolute path"
                )

    def test_no_protocol_prefix_in_nav(self, compiled_reports: dict[str, str]) -> None:
        """Navigation links contain no protocol prefixes (http://, https://)."""
        for filename, content in compiled_reports.items():
            nav_match = re.search(
                r'<nav class="tj-nav-header">(.*?)</nav>',
                content,
                re.DOTALL,
            )
            if nav_match is None:
                continue
            nav_content = nav_match.group(1)

            # Extract all href values
            hrefs = re.findall(r'href="([^"]*)"', nav_content)
            for href in hrefs:
                assert not re.match(r"^https?://", href), (
                    f"{filename}: nav link '{href}' uses protocol prefix"
                )

    def test_active_report_has_nav_active_class(
        self, compiled_reports: dict[str, str]
    ) -> None:
        """Each report's own link in the nav header has class 'nav-active'.

        Validates: Requirement 5.3 — visually distinct style for the
        currently active report's link.
        """
        report_filenames = [f for f in compiled_reports if f != "index.html"]

        for filename in report_filenames:
            content = compiled_reports[filename]
            nav_match = re.search(
                r'<nav class="tj-nav-header">(.*?)</nav>',
                content,
                re.DOTALL,
            )
            assert nav_match is not None, f"{filename} has no nav header"
            nav_content = nav_match.group(1)

            # The link to the current report should have nav-active class
            active_pattern = rf'href="{re.escape(filename)}" class="nav-active"'
            assert re.search(active_pattern, nav_content), (
                f"{filename}: own link does not have 'nav-active' class"
            )
