"""Integration tests for manual trigger scripts.

These tests validate the structure and behavior patterns of the manual trigger
scripts (rebuild.sh, collect-timesheets.sh, send-reminders.sh) by inspecting
their content for correct container names, lock file paths, docker exec commands,
and colored output patterns.

Actual Docker-based execution would happen in a CI environment with running
containers. These tests verify the scripts are correctly structured.

Requirements: 10.1, 10.2, 10.3, 10.5, 10.6
"""

import os
import stat
from pathlib import Path

import pytest

# Root of the repository
REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"

# Script definitions: (filename, target_container, lock_file, internal_script)
SCRIPT_CONFIGS = [
    (
        "rebuild.sh",
        "tj-core",
        "/tmp/tj-compile.lock",
        "/app/scripts/compile.sh",
    ),
    (
        "collect-timesheets.sh",
        "tj-mail",
        "/tmp/tj-timesheets.lock",
        "/app/scripts/collect-timesheets.sh",
    ),
    (
        "send-reminders.sh",
        "tj-mail",
        "/tmp/tj-reminders.lock",
        "/app/scripts/send-reminders.sh",
    ),
]

# ANSI color escape codes used in the scripts
ANSI_COLORS = {
    "BLUE": r"\033[34m",
    "GREEN": r"\033[32m",
    "RED": r"\033[31m",
    "YELLOW": r"\033[33m",
    "RESET": r"\033[0m",
}


@pytest.fixture(params=SCRIPT_CONFIGS, ids=lambda c: c[0])
def script_config(request: pytest.FixtureRequest) -> tuple[str, str, str, str]:
    """Parametrize over all three manual trigger scripts."""
    return request.param


@pytest.fixture
def script_path(script_config: tuple[str, str, str, str]) -> Path:
    """Return the full path to the script file."""
    return SCRIPTS_DIR / script_config[0]


@pytest.fixture
def script_content(script_path: Path) -> str:
    """Read and return the script content."""
    return script_path.read_text(encoding="utf-8")


class TestScriptsExistAndExecutable:
    """Verify all three scripts exist and are executable."""

    def test_script_exists(self, script_path: Path) -> None:
        """Script file must exist in the scripts/ directory."""
        assert script_path.exists(), f"Script not found: {script_path}"

    def test_script_is_file(self, script_path: Path) -> None:
        """Script must be a regular file."""
        assert script_path.is_file(), f"Not a regular file: {script_path}"

    @pytest.mark.skipif(os.name == "nt", reason="File permissions not applicable on Windows")
    def test_script_is_executable(self, script_path: Path) -> None:
        """Script must have executable permission set."""
        mode = script_path.stat().st_mode
        assert mode & stat.S_IXUSR, f"Script is not executable: {script_path}"

    def test_script_has_bash_shebang(self, script_content: str) -> None:
        """Script must start with a bash shebang line."""
        assert script_content.startswith("#!/usr/bin/env bash"), (
            "Script must have #!/usr/bin/env bash shebang"
        )

    def test_script_uses_strict_mode(self, script_content: str) -> None:
        """Script must use set -euo pipefail for strict error handling."""
        assert "set -euo pipefail" in script_content


class TestDockerCliCheck:
    """Verify scripts check for Docker CLI availability."""

    def test_checks_docker_command(self, script_content: str) -> None:
        """Script must check that the docker command is available."""
        assert "command -v docker" in script_content

    def test_docker_not_found_exits_with_error(self, script_content: str) -> None:
        """Script must exit with code 1 when Docker CLI is not found."""
        # The check block should exit 1 on failure
        assert "exit 1" in script_content
        assert "Docker CLI is not available" in script_content

    def test_docker_not_found_shows_install_link(self, script_content: str) -> None:
        """Script must provide Docker installation guidance."""
        assert "https://docs.docker.com/get-docker/" in script_content


class TestContainerRunningCheck:
    """Verify scripts check for the correct container name."""

    def test_checks_correct_container(
        self, script_content: str, script_config: tuple[str, str, str, str]
    ) -> None:
        """Script must check that the target container is running."""
        _, container, _, _ = script_config
        assert f'CONTAINER="{container}"' in script_content

    def test_uses_docker_inspect(self, script_content: str) -> None:
        """Script must use docker inspect to check container state."""
        assert "docker inspect" in script_content
        assert "{{.State.Running}}" in script_content

    def test_container_not_running_exits_1(self, script_content: str) -> None:
        """Script must exit 1 when target container is not running."""
        assert "is not running" in script_content

    def test_container_not_running_shows_guidance(self, script_content: str) -> None:
        """Script must suggest docker compose up -d when container is not running."""
        assert "docker compose up -d" in script_content


class TestLockFileCheck:
    """Verify scripts check the correct lock file path."""

    def test_defines_correct_lock_file(
        self, script_content: str, script_config: tuple[str, str, str, str]
    ) -> None:
        """Script must define the correct lock file path for its operation."""
        _, _, lock_file, _ = script_config
        assert f'LOCK_FILE="{lock_file}"' in script_content

    def test_checks_lock_file_in_container(self, script_content: str) -> None:
        """Script must check for lock file existence inside the container."""
        assert "docker exec" in script_content
        assert "test -f" in script_content

    def test_lock_file_exists_exits_1(self, script_content: str) -> None:
        """Script must exit 1 when lock file exists (operation in progress)."""
        assert "already in progress" in script_content

    def test_lock_file_shows_timestamp(self, script_content: str) -> None:
        """Script must display lock file info (timestamp) when lock exists."""
        # The script reads the lock file content which contains the timestamp
        assert "cat" in script_content and "LOCK_FILE" in script_content

    def test_lock_file_shows_removal_hint(self, script_content: str) -> None:
        """Script must show how to remove a stale lock file."""
        assert "rm $LOCK_FILE" in script_content or "rm ${LOCK_FILE}" in script_content


class TestDockerExecCommand:
    """Verify scripts use the correct docker exec command."""

    def test_uses_docker_exec(self, script_content: str) -> None:
        """Script must use docker exec to run the operation."""
        assert "docker exec" in script_content

    def test_executes_correct_internal_script(
        self, script_content: str, script_config: tuple[str, str, str, str]
    ) -> None:
        """Script must execute the correct internal script path."""
        _, _, _, internal_script = script_config
        assert f'SCRIPT="{internal_script}"' in script_content

    def test_exec_targets_correct_container(
        self, script_content: str, script_config: tuple[str, str, str, str]
    ) -> None:
        """Script must docker exec into the correct container."""
        _, container, _, _ = script_config
        # The script uses $CONTAINER variable in docker exec
        assert 'docker exec "$CONTAINER"' in script_content


class TestColoredOutput:
    """Verify scripts produce colored output with ANSI escape codes."""

    def test_defines_blue_color(self, script_content: str) -> None:
        """Script must define blue color for 'starting' indicator."""
        assert r"\033[34m" in script_content

    def test_defines_green_color(self, script_content: str) -> None:
        """Script must define green color for 'success' indicator."""
        assert r"\033[32m" in script_content

    def test_defines_red_color(self, script_content: str) -> None:
        """Script must define red color for 'failure' indicator."""
        assert r"\033[31m" in script_content

    def test_defines_yellow_color(self, script_content: str) -> None:
        """Script must define yellow color for 'warning' indicator."""
        assert r"\033[33m" in script_content

    def test_defines_reset_code(self, script_content: str) -> None:
        """Script must define ANSI reset code."""
        assert r"\033[0m" in script_content

    def test_uses_arrow_for_starting(self, script_content: str) -> None:
        """Script must use → symbol with blue color for operation start."""
        assert "→" in script_content

    def test_uses_checkmark_for_success(self, script_content: str) -> None:
        """Script must use ✓ symbol with green color for success."""
        assert "✓" in script_content

    def test_uses_cross_for_failure(self, script_content: str) -> None:
        """Script must use ✗ symbol with red color for failure."""
        assert "✗" in script_content

    def test_uses_warning_symbol(self, script_content: str) -> None:
        """Script must use ⚠ symbol with yellow color for warnings."""
        assert "⚠" in script_content


class TestScriptIndependence:
    """Verify scripts work independently of tj-cron container."""

    def test_no_dependency_on_cron_container(self, script_content: str) -> None:
        """Script must not reference or depend on the tj-cron container."""
        # Scripts should only reference their target container, not tj-cron
        assert "tj-cron" not in script_content

    def test_uses_docker_exec_directly(self, script_content: str) -> None:
        """Script must use docker exec directly, not via cron service."""
        # Verify the script calls docker exec on its own, not through another service
        lines_with_exec = [
            line for line in script_content.splitlines() if "docker exec" in line
        ]
        assert len(lines_with_exec) >= 2, (
            "Script should have at least 2 docker exec calls "
            "(lock check + execution)"
        )
