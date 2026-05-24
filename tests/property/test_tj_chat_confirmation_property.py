"""Property-based tests for write confirmation summaries.

**Validates: Requirements 7.1**

Property 17: Write confirmation summary contains required information.
- For any proposed write operation, the confirmation summary presented to the
  user SHALL contain the target file path, the type of operation (create,
  modify, or delete), and a non-empty description of the content change.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.models import ToolCall
from tj_chat.settings import ChatSettings
from tj_chat.tool_executor import ToolExecutor

# Strategy for valid file path segments (no path traversal, no special chars)
_path_segment = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"),
        whitelist_characters="_-.",
    ),
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip(".") != "" and ".." not in s)

# Windows reserved device names that always "exist" as special files
_WINDOWS_RESERVED = frozenset({
    "con", "prn", "aux", "nul",
    "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
    "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9",
})

# Strategy for relative file paths within the project
_relative_path = st.builds(
    lambda segments: "/".join(segments),
    segments=st.lists(_path_segment, min_size=1, max_size=3),
).filter(
    lambda p: ".." not in p
    and p.strip() != ""
    and p.split("/")[-1].split(".")[0].lower() not in _WINDOWS_RESERVED
)

# Strategy for non-empty file content
_file_content = st.text(min_size=1, max_size=200).filter(lambda s: s.strip() != "")

# Strategy for operation types that write_file can produce
_OPERATION_KEYWORDS = {"create", "modify", "Create", "Modify", "write", "Write", "add", "Add", "update", "Update"}


def _run_async(coro):
    """Run an async coroutine synchronously."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class TestWriteConfirmationSummary:
    """Property 17: Write confirmation summary contains required information.

    **Validates: Requirements 7.1**
    """

    @given(
        path=_relative_path,
        content=_file_content,
    )
    @settings(max_examples=100)
    def test_write_file_create_summary_contains_path_and_operation(
        self, path: str, content: str
    ) -> None:
        """write_file on a non-existing file produces summary with path and 'create' operation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            chat_settings = ChatSettings(
                project_path=project_dir,
                project_file="project.tjp",
            )
            executor = ToolExecutor(project_dir, chat_settings)

            captured_summary: str | None = None

            async def capture_confirm(summary: str) -> bool:
                nonlocal captured_summary
                captured_summary = summary
                return False  # Decline to avoid actual writes

            tool_call = ToolCall(
                id="test-call-1",
                name="write_file",
                arguments={"path": path, "content": content},
            )

            _run_async(executor.execute(tool_call, capture_confirm))

            # The summary must have been captured
            assert captured_summary is not None, "confirm_fn was not called"

            # Summary must contain the file path (or a reference to it)
            assert path in captured_summary, (
                f"Summary does not contain file path '{path}': {captured_summary}"
            )

            # Summary must indicate the operation type (create for new file)
            summary_lower = captured_summary.lower()
            assert "create" in summary_lower, (
                f"Summary does not indicate 'create' operation: {captured_summary}"
            )

            # Summary must be non-empty (it already is if we got here, but be explicit)
            assert len(captured_summary.strip()) > 0

    @given(
        path=_relative_path,
        content=_file_content,
    )
    @settings(max_examples=100)
    def test_write_file_modify_summary_contains_path_and_operation(
        self, path: str, content: str
    ) -> None:
        """write_file on an existing file produces summary with path and 'modify' operation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            chat_settings = ChatSettings(
                project_path=project_dir,
                project_file="project.tjp",
            )
            executor = ToolExecutor(project_dir, chat_settings)

            # Create the file first so the operation is "modify"
            target = project_dir / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("original content", encoding="utf-8")

            captured_summary: str | None = None

            async def capture_confirm(summary: str) -> bool:
                nonlocal captured_summary
                captured_summary = summary
                return False  # Decline to avoid actual writes

            tool_call = ToolCall(
                id="test-call-2",
                name="write_file",
                arguments={"path": path, "content": content},
            )

            _run_async(executor.execute(tool_call, capture_confirm))

            assert captured_summary is not None, "confirm_fn was not called"

            # Summary must contain the file path
            assert path in captured_summary, (
                f"Summary does not contain file path '{path}': {captured_summary}"
            )

            # Summary must indicate the operation type (modify for existing file)
            summary_lower = captured_summary.lower()
            assert "modify" in summary_lower, (
                f"Summary does not indicate 'modify' operation: {captured_summary}"
            )

            # Summary must be non-empty
            assert len(captured_summary.strip()) > 0

    @given(
        path=_relative_path,
        content=_file_content,
    )
    @settings(max_examples=100)
    def test_write_file_summary_is_non_empty_description(
        self, path: str, content: str
    ) -> None:
        """write_file confirmation summary is a non-empty description of the change."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            chat_settings = ChatSettings(
                project_path=project_dir,
                project_file="project.tjp",
            )
            executor = ToolExecutor(project_dir, chat_settings)

            captured_summary: str | None = None

            async def capture_confirm(summary: str) -> bool:
                nonlocal captured_summary
                captured_summary = summary
                return False

            tool_call = ToolCall(
                id="test-call-3",
                name="write_file",
                arguments={"path": path, "content": content},
            )

            _run_async(executor.execute(tool_call, capture_confirm))

            assert captured_summary is not None, "confirm_fn was not called"

            # The summary must be a non-empty description
            # It should contain more than just the path - it should describe the change
            assert len(captured_summary.strip()) > len(path), (
                f"Summary is not a meaningful description: {captured_summary}"
            )

    @given(
        task_path=st.builds(
            lambda parts: ".".join(parts),
            parts=st.lists(
                st.text(
                    alphabet=st.characters(
                        whitelist_categories=("L", "N"),
                        whitelist_characters="_",
                    ),
                    min_size=2,
                    max_size=10,
                ).filter(lambda s: s[0].isalpha()),
                min_size=2,
                max_size=4,
            ),
        ),
        attr_key=st.sampled_from(["effort", "priority", "complete"]),
        attr_value=st.sampled_from(["10d", "500", "100"]),
    )
    @settings(max_examples=100)
    def test_update_task_summary_contains_task_reference_and_operation(
        self, task_path: str, attr_key: str, attr_value: str
    ) -> None:
        """update_task produces summary referencing the task and describing the update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            chat_settings = ChatSettings(
                project_path=project_dir,
                project_file="project.tjp",
            )
            executor = ToolExecutor(project_dir, chat_settings)

            captured_summary: str | None = None

            async def capture_confirm(summary: str) -> bool:
                nonlocal captured_summary
                captured_summary = summary
                return False

            tool_call = ToolCall(
                id="test-call-4",
                name="update_task",
                arguments={
                    "task_path": task_path,
                    "attributes": {attr_key: attr_value},
                },
            )

            _run_async(executor.execute(tool_call, capture_confirm))

            assert captured_summary is not None, "confirm_fn was not called"

            # Summary must reference the task path
            assert task_path in captured_summary, (
                f"Summary does not contain task path '{task_path}': {captured_summary}"
            )

            # Summary must indicate an update/modify operation
            summary_lower = captured_summary.lower()
            assert "update" in summary_lower or "modify" in summary_lower, (
                f"Summary does not indicate update operation: {captured_summary}"
            )

            # Summary must be non-empty
            assert len(captured_summary.strip()) > 0

    @given(
        resource_id=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                whitelist_characters="_",
            ),
            min_size=2,
            max_size=15,
        ).filter(lambda s: s[0].isalpha()),
        attr_key=st.sampled_from(["rate", "workinghours"]),
        attr_value=st.sampled_from(["100", "40h"]),
    )
    @settings(max_examples=100)
    def test_update_resource_summary_contains_resource_and_operation(
        self, resource_id: str, attr_key: str, attr_value: str
    ) -> None:
        """update_resource produces summary referencing the resource and describing the update."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            chat_settings = ChatSettings(
                project_path=project_dir,
                project_file="project.tjp",
            )
            executor = ToolExecutor(project_dir, chat_settings)

            captured_summary: str | None = None

            async def capture_confirm(summary: str) -> bool:
                nonlocal captured_summary
                captured_summary = summary
                return False

            tool_call = ToolCall(
                id="test-call-5",
                name="update_resource",
                arguments={
                    "resource_id": resource_id,
                    "attributes": {attr_key: attr_value},
                },
            )

            _run_async(executor.execute(tool_call, capture_confirm))

            assert captured_summary is not None, "confirm_fn was not called"

            # Summary must reference the resource ID
            assert resource_id in captured_summary, (
                f"Summary does not contain resource ID '{resource_id}': {captured_summary}"
            )

            # Summary must indicate an update/modify operation
            summary_lower = captured_summary.lower()
            assert "update" in summary_lower or "modify" in summary_lower, (
                f"Summary does not indicate update operation: {captured_summary}"
            )

            # Summary must be non-empty
            assert len(captured_summary.strip()) > 0

    @given(
        report_id=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                whitelist_characters="_",
            ),
            min_size=2,
            max_size=15,
        ).filter(lambda s: s[0].isalpha()),
        report_type=st.sampled_from(["taskreport", "resourcereport", "textreport"]),
    )
    @settings(max_examples=100)
    def test_write_report_summary_contains_report_reference_and_operation(
        self, report_id: str, report_type: str
    ) -> None:
        """write_report produces summary referencing the report and describing the write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_dir = Path(tmpdir)
            chat_settings = ChatSettings(
                project_path=project_dir,
                project_file="project.tjp",
            )
            executor = ToolExecutor(project_dir, chat_settings)

            captured_summary: str | None = None

            async def capture_confirm(summary: str) -> bool:
                nonlocal captured_summary
                captured_summary = summary
                return False

            tool_call = ToolCall(
                id="test-call-6",
                name="write_report",
                arguments={
                    "report_id": report_id,
                    "report_type": report_type,
                    "config": {
                        "title": "Test Report",
                        "columns": ["name", "start", "end"],
                    },
                },
            )

            _run_async(executor.execute(tool_call, capture_confirm))

            assert captured_summary is not None, "confirm_fn was not called"

            # Summary must reference the report ID
            assert report_id in captured_summary, (
                f"Summary does not contain report ID '{report_id}': {captured_summary}"
            )

            # Summary must indicate a write operation
            summary_lower = captured_summary.lower()
            assert any(
                kw in summary_lower
                for kw in ("write", "create", "report")
            ), (
                f"Summary does not indicate write/create operation: {captured_summary}"
            )

            # Summary must be non-empty
            assert len(captured_summary.strip()) > 0
