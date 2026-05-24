"""Property-based tests for backup creation before file writes.

**Validates: Requirements 3.6, 7.2**

Property 2: Backup creation before file writes.
- For any file modification operation on an existing project file, the system
  SHALL create a .bak copy of the original file content in the same directory
  before writing the new content, such that the backup file contains
  byte-for-byte identical content to the original.

Property 4: Declined write operations preserve file state.
- For any proposed write operation that the user declines, the target file
  SHALL remain unchanged (byte-for-byte identical to its state before the
  proposal).
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.models import ToolCall
from tj_chat.settings import ChatSettings
from tj_chat.tool_executor import ToolExecutor

# Strategy for file content: printable text with some structure
_file_content = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\x00"),
    min_size=1,
    max_size=500,
)

# Strategy for new content to write (different from original)
_new_content = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\x00"),
    min_size=1,
    max_size=500,
)

# Strategy for a safe filename
_safe_filename = st.text(
    alphabet=st.characters(categories=("L", "N"), exclude_characters="\x00/\\:"),
    min_size=1,
    max_size=12,
).map(lambda s: s + ".tji")


class TestBackupCreationBeforeFileWrites:
    """Property 2: Backup creation before file writes.

    **Validates: Requirements 3.6**
    """

    @given(original_content=_file_content, filename=_safe_filename)
    @settings(max_examples=100)
    def test_backup_is_byte_for_byte_identical_to_original(
        self, original_content: str, filename: str
    ) -> None:
        """For any existing file, create_backup produces a .bak copy identical to the original."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            target_file = project_dir / filename
            target_file.write_text(original_content, encoding="utf-8")

            chat_settings = ChatSettings(
                project_path=project_dir,
                project_file="project.tjp",
            )
            executor = ToolExecutor(project_dir, chat_settings)

            backup_path = executor.create_backup(target_file)

            # Backup must exist
            assert backup_path.exists()
            # Backup must be in the same directory
            assert backup_path.parent == target_file.parent
            # Backup must have .bak extension appended
            assert backup_path.name == filename + ".bak"
            # Backup content must be byte-for-byte identical
            assert backup_path.read_bytes() == target_file.read_bytes()

    @given(original_content=_file_content, new_content=_new_content, filename=_safe_filename)
    @settings(max_examples=50)
    def test_safe_write_creates_backup_before_writing(
        self, original_content: str, new_content: str, filename: str
    ) -> None:
        """The _safe_write method creates a backup of existing files before writing new content."""

        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as tmp_dir:
                project_dir = Path(tmp_dir)
                target_file = project_dir / filename

                # Create the original file
                target_file.write_text(original_content, encoding="utf-8")
                original_bytes = target_file.read_bytes()

                # Create a project file so compiler validation is attempted
                project_file = project_dir / "project.tjp"
                project_file.write_text("project test", encoding="utf-8")

                chat_settings = ChatSettings(
                    project_path=project_dir,
                    project_file="project.tjp",
                )
                executor = ToolExecutor(project_dir, chat_settings)

                # Mock compiler to return success so the write persists
                mock_result = AsyncMock()
                mock_result.return_value = type(
                    "CompilerResult", (), {"success": True, "stdout": "", "stderr": ""}
                )()

                with patch.object(executor, "validate_with_compiler", mock_result):
                    await executor._safe_write("test-id", target_file, new_content)

                # Backup file must exist with original content
                backup_path = target_file.with_suffix(target_file.suffix + ".bak")
                assert backup_path.exists()
                assert backup_path.read_bytes() == original_bytes

        asyncio.run(run_test())


class TestDeclinedWritePreservesFileState:
    """Property 4: Declined write operations preserve file state.

    **Validates: Requirements 7.2**
    """

    @given(original_content=_file_content, new_content=_new_content, filename=_safe_filename)
    @settings(max_examples=100)
    def test_declined_write_preserves_original_file(
        self, original_content: str, new_content: str, filename: str
    ) -> None:
        """When user declines a write, the target file remains unchanged."""

        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as tmp_dir:
                project_dir = Path(tmp_dir)
                target_file = project_dir / filename

                # Create the original file
                target_file.write_text(original_content, encoding="utf-8")
                original_bytes = target_file.read_bytes()

                chat_settings = ChatSettings(
                    project_path=project_dir,
                    project_file="project.tjp",
                )
                executor = ToolExecutor(project_dir, chat_settings)

                # Create a tool call for write_file
                tool_call = ToolCall(
                    id="test-call-1",
                    name="write_file",
                    arguments={"path": filename, "content": new_content},
                )

                # User declines the write
                async def decline_fn(_summary: str) -> bool:
                    return False

                result = await executor.execute(tool_call, decline_fn)

                # Operation should not succeed
                assert not result.success
                assert "declined" in result.content.lower()

                # File must remain unchanged
                assert target_file.read_bytes() == original_bytes

                # No backup should be created for declined operations
                backup_path = target_file.with_suffix(target_file.suffix + ".bak")
                assert not backup_path.exists()

        asyncio.run(run_test())

    @given(original_content=_file_content, new_content=_new_content, filename=_safe_filename)
    @settings(max_examples=50)
    def test_declined_write_on_nonexistent_file_creates_nothing(
        self, original_content: str, new_content: str, filename: str
    ) -> None:
        """When user declines a write for a new file, no file is created."""

        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as tmp_dir:
                project_dir = Path(tmp_dir)
                target_file = project_dir / filename

                chat_settings = ChatSettings(
                    project_path=project_dir,
                    project_file="project.tjp",
                )
                executor = ToolExecutor(project_dir, chat_settings)

                # Create a tool call for write_file (file doesn't exist yet)
                tool_call = ToolCall(
                    id="test-call-2",
                    name="write_file",
                    arguments={"path": filename, "content": new_content},
                )

                # User declines the write
                async def decline_fn(_summary: str) -> bool:
                    return False

                result = await executor.execute(tool_call, decline_fn)

                # Operation should not succeed
                assert not result.success

                # File must not exist
                assert not target_file.exists()

        asyncio.run(run_test())
