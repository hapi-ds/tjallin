"""Unit tests for the tool executor module."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tj_chat.models import CompilerResult, PathSecurityError, ToolCall, ToolResult
from tj_chat.settings import ChatSettings
from tj_chat.tool_executor import ToolExecutor


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory with sample files."""
    project = tmp_path / "project"
    project.mkdir()
    # Create a project file
    (project / "project.tjp").write_text(
        'project acme "Acme Project" 2024-01-01 +26w {\n  now 2024-03-01\n}\n'
    )
    # Create includes directory with tasks
    includes = project / "includes"
    includes.mkdir()
    (includes / "tasks.tji").write_text(
        'task dev "Development" {\n  effort 10d\n  allocate alice\n}\n'
    )
    (includes / "resources.tji").write_text(
        'resource alice "Alice Smith" {\n  rate 100.0\n}\n'
    )
    return project


@pytest.fixture
def settings() -> ChatSettings:
    """Create test settings."""
    return ChatSettings(
        project_path=Path("/tmp/test"),
        project_file="project.tjp",
        default_author="alice",
    )


@pytest.fixture
def executor(project_dir: Path, settings: ChatSettings) -> ToolExecutor:
    """Create a ToolExecutor instance for testing."""
    return ToolExecutor(project_dir, settings)


@pytest.fixture
def confirm_yes() -> AsyncMock:
    """Confirmation callback that always approves."""
    return AsyncMock(return_value=True)


@pytest.fixture
def confirm_no() -> AsyncMock:
    """Confirmation callback that always declines."""
    return AsyncMock(return_value=False)


class TestValidatePath:
    """Tests for validate_path()."""

    def test_valid_relative_path(self, executor: ToolExecutor, project_dir: Path) -> None:
        result = executor.validate_path("includes/tasks.tji")
        expected = (project_dir / "includes" / "tasks.tji").resolve()
        assert result == expected

    def test_path_outside_project_raises(self, executor: ToolExecutor) -> None:
        with pytest.raises(PathSecurityError):
            executor.validate_path("../../etc/passwd")


class TestCreateBackup:
    """Tests for create_backup()."""

    def test_creates_bak_file(self, executor: ToolExecutor, project_dir: Path) -> None:
        target = project_dir / "includes" / "tasks.tji"
        original_content = target.read_text()
        backup = executor.create_backup(target)
        assert backup.exists()
        assert backup.suffix == ".bak"
        assert backup.read_text() == original_content

    def test_backup_path_has_correct_name(
        self, executor: ToolExecutor, project_dir: Path
    ) -> None:
        target = project_dir / "includes" / "tasks.tji"
        backup = executor.create_backup(target)
        assert backup.name == "tasks.tji.bak"
        assert backup.parent == target.parent


class TestExecuteUnknownTool:
    """Tests for unknown tool handling."""

    def test_unknown_tool_returns_error(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(id="tc1", name="nonexistent_tool", arguments={})
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is False
        assert "Unknown tool" in result.content


class TestReadFile:
    """Tests for read_file tool."""

    def test_read_existing_file(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(
            id="tc1", name="read_file", arguments={"path": "includes/tasks.tji"}
        )
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is True
        assert "task dev" in result.content

    def test_read_nonexistent_file(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(
            id="tc1", name="read_file", arguments={"path": "nonexistent.tji"}
        )
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is False
        assert "not found" in result.content.lower()

    def test_read_file_outside_project(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(
            id="tc1", name="read_file", arguments={"path": "../../etc/passwd"}
        )
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is False


class TestListFiles:
    """Tests for list_files tool."""

    def test_list_all_files(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(id="tc1", name="list_files", arguments={})
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is True
        assert "project.tjp" in result.content
        assert "includes/tasks.tji" in result.content

    def test_list_subdirectory(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(
            id="tc1", name="list_files", arguments={"subdirectory": "includes"}
        )
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is True
        assert "tasks.tji" in result.content


class TestListTasks:
    """Tests for list_tasks tool."""

    def test_list_tasks_returns_tasks(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(id="tc1", name="list_tasks", arguments={})
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is True
        assert "dev" in result.content
        assert "Development" in result.content


class TestListResources:
    """Tests for list_resources tool."""

    def test_list_resources_returns_resources(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(id="tc1", name="list_resources", arguments={})
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is True
        assert "alice" in result.content
        assert "Alice Smith" in result.content


class TestFindTask:
    """Tests for find_task tool."""

    def test_find_task_with_match(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(
            id="tc1", name="find_task", arguments={"query": "dev"}
        )
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is True
        assert "dev" in result.content

    def test_find_task_missing_query(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(id="tc1", name="find_task", arguments={})
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is False
        assert "query" in result.content.lower()


class TestWriteFile:
    """Tests for write_file tool with safety checks."""

    def test_write_declined_preserves_file(
        self, executor: ToolExecutor, confirm_no: AsyncMock, project_dir: Path
    ) -> None:
        original = (project_dir / "includes" / "tasks.tji").read_text()
        tool_call = ToolCall(
            id="tc1",
            name="write_file",
            arguments={"path": "includes/tasks.tji", "content": "new content"},
        )
        result = asyncio.run(executor.execute(tool_call, confirm_no))
        assert result.success is False
        assert "declined" in result.content.lower()
        # File unchanged
        assert (project_dir / "includes" / "tasks.tji").read_text() == original

    @patch("tj_chat.tool_executor.ToolExecutor.validate_with_compiler")
    def test_write_creates_backup(
        self,
        mock_compiler: AsyncMock,
        executor: ToolExecutor,
        confirm_yes: AsyncMock,
        project_dir: Path,
    ) -> None:
        mock_compiler.return_value = CompilerResult(
            success=True, stdout="", stderr=""
        )
        original = (project_dir / "includes" / "tasks.tji").read_text()
        tool_call = ToolCall(
            id="tc1",
            name="write_file",
            arguments={"path": "includes/tasks.tji", "content": "updated"},
        )
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is True
        # Backup exists with original content
        backup = project_dir / "includes" / "tasks.tji.bak"
        assert backup.exists()
        assert backup.read_text() == original

    @patch("tj_chat.tool_executor.ToolExecutor.validate_with_compiler")
    def test_write_rollback_on_compile_failure(
        self,
        mock_compiler: AsyncMock,
        executor: ToolExecutor,
        confirm_yes: AsyncMock,
        project_dir: Path,
    ) -> None:
        mock_compiler.return_value = CompilerResult(
            success=False, stdout="", stderr="Error: syntax error"
        )
        original = (project_dir / "includes" / "tasks.tji").read_text()
        tool_call = ToolCall(
            id="tc1",
            name="write_file",
            arguments={"path": "includes/tasks.tji", "content": "bad content"},
        )
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is False
        assert "rolled back" in result.content.lower()
        # File restored to original
        assert (project_dir / "includes" / "tasks.tji").read_text() == original


class TestSearchTjDocs:
    """Tests for search_tj_docs tool."""

    def test_search_without_docs_service(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(
            id="tc1", name="search_tj_docs", arguments={"query": "task"}
        )
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is False
        assert "not available" in result.content.lower()

    def test_search_missing_query(
        self, executor: ToolExecutor, confirm_yes: AsyncMock
    ) -> None:
        tool_call = ToolCall(id="tc1", name="search_tj_docs", arguments={})
        result = asyncio.run(executor.execute(tool_call, confirm_yes))
        assert result.success is False
        assert "query" in result.content.lower()
