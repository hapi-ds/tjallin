"""Unit tests for EditorService.

Tests file tree building with various directory structures, verifying
sorting, hidden file exclusion, file type classification, and path safety.
Also tests file read operations with path validation and error handling,
and save workflow with compiler validation, backup, and error scenarios.
"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from tj_chat.editor_service import EditorService
from tj_chat.settings import ChatSettings


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a temporary project directory with sample files."""
    # Create directories
    (tmp_path / "subdir_a").mkdir()
    (tmp_path / "subdir_b").mkdir()
    (tmp_path / "subdir_a" / "nested").mkdir()

    # Create files
    (tmp_path / "project.tjp").write_text("project content")
    (tmp_path / "tasks.tji").write_text("tasks content")
    (tmp_path / "readme.md").write_text("readme")
    (tmp_path / "subdir_a" / "sub_tasks.tji").write_text("sub tasks")
    (tmp_path / "subdir_a" / "nested" / "deep.tjp").write_text("deep")

    # Create hidden entries (should be excluded)
    (tmp_path / ".git").mkdir()
    (tmp_path / ".hidden_file").write_text("hidden")
    (tmp_path / "subdir_a" / ".secret").write_text("secret")

    return tmp_path


@pytest.fixture
def settings(project_dir: Path) -> ChatSettings:
    """Create ChatSettings pointing to the temp project directory."""
    return ChatSettings(project_path=project_dir)


@pytest.fixture
def service(project_dir: Path, settings: ChatSettings) -> EditorService:
    """Create an EditorService instance."""
    return EditorService(project_dir=project_dir, settings=settings)


class TestBuildFileTree:
    """Tests for EditorService.build_file_tree()."""

    def test_returns_list_of_file_nodes(self, service: EditorService) -> None:
        """build_file_tree returns a list."""
        tree = service.build_file_tree()
        assert isinstance(tree, list)
        assert len(tree) > 0

    def test_excludes_hidden_entries(self, service: EditorService) -> None:
        """Hidden files and directories (starting with '.') are excluded."""
        tree = service.build_file_tree()
        names = [node.name for node in tree]
        assert ".git" not in names
        assert ".hidden_file" not in names

    def test_excludes_hidden_entries_in_subdirectories(
        self, service: EditorService
    ) -> None:
        """Hidden entries in subdirectories are also excluded."""
        tree = service.build_file_tree()
        subdir_a = next(n for n in tree if n.name == "subdir_a")
        child_names = [c.name for c in subdir_a.children]
        assert ".secret" not in child_names

    def test_directories_sorted_before_files(
        self, service: EditorService
    ) -> None:
        """Directories appear before files at the top level."""
        tree = service.build_file_tree()
        saw_file = False
        for node in tree:
            if not node.is_directory:
                saw_file = True
            elif saw_file:
                pytest.fail(
                    f"Directory '{node.name}' appeared after a file"
                )

    def test_alphabetical_sort_case_insensitive(
        self, service: EditorService, project_dir: Path
    ) -> None:
        """Entries are sorted alphabetically, case-insensitive."""
        # Add entries with mixed case
        (project_dir / "Zebra.tjp").write_text("z")
        (project_dir / "alpha.tji").write_text("a")

        tree = service.build_file_tree()
        file_names = [n.name for n in tree if not n.is_directory]
        # Should be sorted case-insensitively
        assert file_names == sorted(file_names, key=str.lower)

    def test_file_type_classification_tjp(
        self, service: EditorService
    ) -> None:
        """Files with .tjp extension are classified as 'tjp'."""
        tree = service.build_file_tree()
        tjp_node = next(n for n in tree if n.name == "project.tjp")
        assert tjp_node.file_type == "tjp"

    def test_file_type_classification_tji(
        self, service: EditorService
    ) -> None:
        """Files with .tji extension are classified as 'tji'."""
        tree = service.build_file_tree()
        tji_node = next(n for n in tree if n.name == "tasks.tji")
        assert tji_node.file_type == "tji"

    def test_file_type_classification_other(
        self, service: EditorService
    ) -> None:
        """Files with other extensions are classified as 'other'."""
        tree = service.build_file_tree()
        md_node = next(n for n in tree if n.name == "readme.md")
        assert md_node.file_type == "other"

    def test_directories_have_file_type_other(
        self, service: EditorService
    ) -> None:
        """Directories always have file_type 'other'."""
        tree = service.build_file_tree()
        for node in tree:
            if node.is_directory:
                assert node.file_type == "other"

    def test_recursive_children(self, service: EditorService) -> None:
        """Subdirectories contain their children recursively."""
        tree = service.build_file_tree()
        subdir_a = next(n for n in tree if n.name == "subdir_a")
        assert subdir_a.is_directory
        assert len(subdir_a.children) > 0

        nested = next(
            c for c in subdir_a.children if c.name == "nested"
        )
        assert nested.is_directory
        assert any(c.name == "deep.tjp" for c in nested.children)

    def test_relative_paths(
        self, service: EditorService
    ) -> None:
        """File nodes have paths relative to the project root."""
        tree = service.build_file_tree()
        tjp_node = next(n for n in tree if n.name == "project.tjp")
        assert tjp_node.path == "project.tjp"

        subdir_a = next(n for n in tree if n.name == "subdir_a")
        assert subdir_a.path == "subdir_a"

    def test_nested_relative_paths(self, service: EditorService) -> None:
        """Nested file nodes have correct relative paths."""
        tree = service.build_file_tree()
        subdir_a = next(n for n in tree if n.name == "subdir_a")
        sub_tasks = next(
            c for c in subdir_a.children if c.name == "sub_tasks.tji"
        )
        # On Windows, relative_to produces backslash paths
        assert sub_tasks.path.replace("\\", "/") == "subdir_a/sub_tasks.tji"

    def test_empty_directory(self, tmp_path: Path) -> None:
        """An empty project directory returns an empty list."""
        settings = ChatSettings(project_path=tmp_path)
        service = EditorService(project_dir=tmp_path, settings=settings)
        tree = service.build_file_tree()
        assert tree == []

    def test_directory_with_only_hidden_files(self, tmp_path: Path) -> None:
        """A directory with only hidden files returns an empty list."""
        (tmp_path / ".gitignore").write_text("*")
        (tmp_path / ".env").write_text("SECRET=x")
        settings = ChatSettings(project_path=tmp_path)
        service = EditorService(project_dir=tmp_path, settings=settings)
        tree = service.build_file_tree()
        assert tree == []


class TestReadFile:
    """Tests for EditorService.read_file()."""

    @pytest.mark.asyncio
    async def test_read_existing_file(self, service: EditorService) -> None:
        """Reading an existing file returns its content with success=True."""
        result = await service.read_file("project.tjp")
        assert result.success is True
        assert result.content == "project content"
        assert result.path == "project.tjp"
        assert result.error is None

    @pytest.mark.asyncio
    async def test_read_file_in_subdirectory(
        self, service: EditorService
    ) -> None:
        """Reading a file in a subdirectory works with relative path."""
        result = await service.read_file("subdir_a/sub_tasks.tji")
        assert result.success is True
        assert result.content == "sub tasks"
        assert result.path == "subdir_a/sub_tasks.tji"

    @pytest.mark.asyncio
    async def test_read_nonexistent_file(
        self, service: EditorService
    ) -> None:
        """Reading a nonexistent file returns success=False with error."""
        result = await service.read_file("nonexistent.tjp")
        assert result.success is False
        assert result.content == ""
        assert result.error is not None
        assert "Failed to read file" in result.error

    @pytest.mark.asyncio
    async def test_read_file_outside_project_boundary(
        self, service: EditorService
    ) -> None:
        """Reading a path that escapes the project boundary returns security error."""
        result = await service.read_file("../outside.txt")
        assert result.success is False
        assert result.content == ""
        assert result.error is not None
        assert "Security error" in result.error

    @pytest.mark.asyncio
    async def test_read_file_path_with_dotdot_traversal(
        self, service: EditorService
    ) -> None:
        """Path traversal attempts are rejected by PathSafetyModule."""
        result = await service.read_file("subdir_a/../../etc/passwd")
        assert result.success is False
        assert "Security error" in result.error

    @pytest.mark.asyncio
    async def test_read_file_preserves_relative_path_in_result(
        self, service: EditorService
    ) -> None:
        """The returned FileContent.path matches the input relative_path."""
        result = await service.read_file("tasks.tji")
        assert result.path == "tasks.tji"

    @pytest.mark.asyncio
    async def test_read_directory_returns_error(
        self, service: EditorService
    ) -> None:
        """Attempting to read a directory returns an error."""
        result = await service.read_file("subdir_a")
        assert result.success is False
        assert result.error is not None


class TestSaveFile:
    """Tests for EditorService.save_file() workflow."""

    @pytest.fixture
    def save_project_dir(self, tmp_path: Path) -> Path:
        """Create a project directory with a .tjp file for save tests."""
        (tmp_path / "project.tjp").write_text("original content")
        (tmp_path / "tasks.tji").write_text("task content")
        return tmp_path

    @pytest.fixture
    def save_service(self, save_project_dir: Path) -> EditorService:
        """Create an EditorService for save tests."""
        settings = ChatSettings(project_path=save_project_dir)
        return EditorService(project_dir=save_project_dir, settings=settings)

    @pytest.mark.asyncio
    async def test_save_success_persists_content(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """On compiler success, new content is persisted to the target file."""
        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await save_service.save_file("project.tjp", "new content")

        assert result.success is True
        assert (save_project_dir / "project.tjp").read_text() == "new content"

    @pytest.mark.asyncio
    async def test_save_success_creates_backup(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """On compiler success, a .bak backup of the original is created."""
        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await save_service.save_file("project.tjp", "new content")

        assert result.success is True
        assert result.backup_path is not None
        bak_file = save_project_dir / result.backup_path
        assert bak_file.exists()
        assert bak_file.read_text() == "original content"

    @pytest.mark.asyncio
    async def test_save_success_removes_temp_file(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """On compiler success, the temp file is removed."""
        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            await save_service.save_file("project.tjp", "new content")

        # No .tmp file should remain
        tmp_files = list(save_project_dir.glob("*.tmp"))
        assert tmp_files == []

    @pytest.mark.asyncio
    async def test_save_new_file_no_backup(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """Saving a new file (doesn't exist yet) creates no backup."""
        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            result = await save_service.save_file("new_file.tjp", "content")

        assert result.success is True
        assert result.backup_path is None
        assert (save_project_dir / "new_file.tjp").read_text() == "content"

    @pytest.mark.asyncio
    async def test_save_compiler_failure_returns_errors(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """On compiler failure, errors from stderr are returned."""
        stderr_output = b"Error: line 3: syntax error\nError: line 5: unknown keyword"
        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", stderr_output))
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            result = await save_service.save_file("project.tjp", "bad content")

        assert result.success is False
        assert len(result.errors) == 2
        assert "syntax error" in result.errors[0]

    @pytest.mark.asyncio
    async def test_save_compiler_failure_preserves_original(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """On compiler failure, the original file content is unchanged."""
        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            await save_service.save_file("project.tjp", "bad content")

        assert (save_project_dir / "project.tjp").read_text() == "original content"

    @pytest.mark.asyncio
    async def test_save_compiler_failure_removes_temp(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """On compiler failure, the temp file is cleaned up."""
        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            await save_service.save_file("project.tjp", "bad content")

        tmp_files = list(save_project_dir.glob("*.tmp"))
        assert tmp_files == []

    @pytest.mark.asyncio
    async def test_save_compiler_failure_no_backup_created(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """On compiler failure, no backup file is created."""
        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_proc.returncode = 1
            mock_exec.return_value = mock_proc

            result = await save_service.save_file("project.tjp", "bad content")

        assert result.backup_path is None
        bak_files = list(save_project_dir.glob("*.bak"))
        assert bak_files == []

    @pytest.mark.asyncio
    async def test_save_path_outside_boundary_rejected(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """Paths outside the project boundary are rejected with security error."""
        result = await save_service.save_file(
            "../outside.tjp", "malicious content"
        )

        assert result.success is False
        assert any("Security error" in e for e in result.errors)

    @pytest.mark.asyncio
    async def test_save_timeout_returns_error(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """Compiler timeout returns a timeout error and cleans up."""
        import asyncio
        from unittest.mock import MagicMock

        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(
                side_effect=asyncio.TimeoutError()
            )
            # kill() is synchronous on real subprocess.Process
            mock_proc.kill = MagicMock()
            mock_proc.wait = AsyncMock()
            mock_exec.return_value = mock_proc

            result = await save_service.save_file("project.tjp", "content")

        assert result.success is False
        assert any("timed out" in e.lower() for e in result.errors)
        # Original file unchanged
        assert (save_project_dir / "project.tjp").read_text() == "original content"

    @pytest.mark.asyncio
    async def test_save_compiler_not_found_returns_error(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """Missing tj3 binary returns an appropriate error."""
        with patch(
            "tj_chat.editor_service.asyncio.create_subprocess_exec",
            side_effect=FileNotFoundError("tj3 not found"),
        ):
            result = await save_service.save_file("project.tjp", "content")

        assert result.success is False
        assert any("not found" in e.lower() for e in result.errors)

    @pytest.mark.asyncio
    async def test_save_backup_failure_aborts(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """If backup creation fails, the save is aborted."""
        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            with patch("tj_chat.editor_service.shutil.copy2") as mock_copy:
                mock_copy.side_effect = OSError("Permission denied")
                result = await save_service.save_file(
                    "project.tjp", "new content"
                )

        assert result.success is False
        assert any("Backup creation failed" in e for e in result.errors)
        # Original file should be unchanged
        assert (save_project_dir / "project.tjp").read_text() == "original content"

    @pytest.mark.asyncio
    async def test_save_invokes_tj3_with_temp_file(
        self, save_service: EditorService, save_project_dir: Path
    ) -> None:
        """The compiler is invoked with the temp file path."""
        with patch("tj_chat.editor_service.asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            mock_exec.return_value = mock_proc

            await save_service.save_file("project.tjp", "content")

        # Verify tj3 was called
        mock_exec.assert_called_once()
        call_args = mock_exec.call_args
        assert call_args[0][0] == "tj3"
        # Second arg should be the temp file path (ends with .tmp)
        assert call_args[0][1].endswith(".tmp")
