"""Property-based tests for compiler safety (rollback on failure).

**Validates: Requirements 3.5**

Property 3: Failed compilation preserves original file.
- For any proposed file modification that causes tj3 to return errors,
  the original file SHALL remain unchanged (byte-for-byte identical to
  its state before the write attempt).
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.models import CompilerResult, ToolCall
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

# Strategy for compiler error messages
_error_message = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\x00"),
    min_size=1,
    max_size=200,
)


class TestFailedCompilationPreservesOriginalFile:
    """Property 3: Failed compilation preserves original file.

    **Validates: Requirements 3.5**
    """

    @given(
        original_content=_file_content,
        new_content=_new_content,
        filename=_safe_filename,
        error_msg=_error_message,
    )
    @settings(max_examples=100)
    def test_failed_compilation_restores_original_via_safe_write(
        self,
        original_content: str,
        new_content: str,
        filename: str,
        error_msg: str,
    ) -> None:
        """When compiler fails after write, original file content is restored."""

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

                # Mock compiler to return failure
                failed_result = CompilerResult(
                    success=False,
                    stdout="",
                    stderr=error_msg,
                )
                mock_validate = AsyncMock(return_value=failed_result)

                with patch.object(executor, "validate_with_compiler", mock_validate):
                    result = await executor._safe_write(
                        "test-id", target_file, new_content
                    )

                # The write should fail
                assert not result.success
                assert "rolled back" in result.content.lower()

                # Original file must be restored byte-for-byte
                assert target_file.read_bytes() == original_bytes

        asyncio.run(run_test())

    @given(
        original_content=_file_content,
        new_content=_new_content,
        filename=_safe_filename,
        error_msg=_error_message,
    )
    @settings(max_examples=50)
    def test_failed_compilation_removes_backup_after_restore(
        self,
        original_content: str,
        new_content: str,
        filename: str,
        error_msg: str,
    ) -> None:
        """When compiler fails and rollback occurs, the backup file is cleaned up."""

        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as tmp_dir:
                project_dir = Path(tmp_dir)
                target_file = project_dir / filename

                # Create the original file
                target_file.write_text(original_content, encoding="utf-8")

                # Create a project file so compiler validation is attempted
                project_file = project_dir / "project.tjp"
                project_file.write_text("project test", encoding="utf-8")

                chat_settings = ChatSettings(
                    project_path=project_dir,
                    project_file="project.tjp",
                )
                executor = ToolExecutor(project_dir, chat_settings)

                # Mock compiler to return failure
                failed_result = CompilerResult(
                    success=False,
                    stdout="",
                    stderr=error_msg,
                )
                mock_validate = AsyncMock(return_value=failed_result)

                with patch.object(executor, "validate_with_compiler", mock_validate):
                    await executor._safe_write("test-id", target_file, new_content)

                # Backup should be cleaned up after rollback
                backup_path = target_file.with_suffix(target_file.suffix + ".bak")
                assert not backup_path.exists()

        asyncio.run(run_test())

    @given(
        new_content=_new_content,
        filename=_safe_filename,
        error_msg=_error_message,
    )
    @settings(max_examples=50)
    def test_failed_compilation_on_new_file_removes_it(
        self,
        new_content: str,
        filename: str,
        error_msg: str,
    ) -> None:
        """When compiler fails for a newly created file, the file is removed."""

        async def run_test() -> None:
            with tempfile.TemporaryDirectory() as tmp_dir:
                project_dir = Path(tmp_dir)
                target_file = project_dir / filename

                # Create a project file so compiler validation is attempted
                project_file = project_dir / "project.tjp"
                project_file.write_text("project test", encoding="utf-8")

                chat_settings = ChatSettings(
                    project_path=project_dir,
                    project_file="project.tjp",
                )
                executor = ToolExecutor(project_dir, chat_settings)

                # Mock compiler to return failure
                failed_result = CompilerResult(
                    success=False,
                    stdout="",
                    stderr=error_msg,
                )
                mock_validate = AsyncMock(return_value=failed_result)

                # File does not exist yet
                assert not target_file.exists()

                with patch.object(executor, "validate_with_compiler", mock_validate):
                    result = await executor._safe_write(
                        "test-id", target_file, new_content
                    )

                # The write should fail
                assert not result.success

                # New file should be removed after failed compilation
                assert not target_file.exists()

        asyncio.run(run_test())

    @given(
        original_content=_file_content,
        new_content=_new_content,
        filename=_safe_filename,
        error_msg=_error_message,
    )
    @settings(max_examples=50)
    def test_failed_compilation_via_write_file_tool_preserves_file(
        self,
        original_content: str,
        new_content: str,
        filename: str,
        error_msg: str,
    ) -> None:
        """End-to-end: write_file tool with compiler failure preserves original."""

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

                # Create a tool call for write_file
                tool_call = ToolCall(
                    id="test-call-1",
                    name="write_file",
                    arguments={"path": filename, "content": new_content},
                )

                # User confirms the write
                async def confirm_fn(_summary: str) -> bool:
                    return True

                # Mock compiler to return failure
                failed_result = CompilerResult(
                    success=False,
                    stdout="",
                    stderr=error_msg,
                )
                mock_validate = AsyncMock(return_value=failed_result)

                with patch.object(executor, "validate_with_compiler", mock_validate):
                    result = await executor.execute(tool_call, confirm_fn)

                # The write should fail
                assert not result.success

                # Original file must be preserved
                assert target_file.read_bytes() == original_bytes

        asyncio.run(run_test())
