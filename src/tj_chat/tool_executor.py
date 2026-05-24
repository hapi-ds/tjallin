"""Tool executor for the LLM Agent Chat service.

Dispatches LLM tool calls to appropriate handlers with path safety
enforcement, backup creation, and compiler validation for write operations.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from tj_chat.generators import (
    JournalEntryGenerator,
    ReportGenerator,
    TaskGenerator,
    TimesheetGenerator,
)
from tj_chat.models import (
    BookingRequest,
    CompilerResult,
    JournalEntryRequest,
    PathSecurityError,
    ReportRequest,
    TaskRequest,
    ToolCall,
    ToolResult,
)
from tj_chat.path_safety import validate_project_path
from tj_chat.project_reader import ProjectReader
from tj_chat.settings import ChatSettings
from tj_chat.tj_docs import TJDocumentationService

# Type alias for the confirmation callback
ConfirmFn = Callable[[str], Awaitable[bool]]


# Tools that perform write operations and require confirmation
_WRITE_TOOLS = frozenset({
    "write_file",
    "update_task",
    "add_task",
    "update_resource",
    "write_timesheet",
    "write_journal",
    "write_report",
})


class ToolExecutor:
    """Executes LLM tool calls with path safety and confirmation.

    Dispatches tool calls to the appropriate handler, enforces path
    boundaries, creates backups before writes, and validates changes
    with the tj3 compiler.

    Args:
        project_dir: Path to the project directory.
        settings: Chat settings configuration.
    """

    def __init__(self, project_dir: Path, settings: ChatSettings) -> None:
        self._project_dir = project_dir
        self._settings = settings
        self._reader = ProjectReader(project_dir)
        self._timesheet_gen = TimesheetGenerator()
        self._journal_gen = JournalEntryGenerator()
        self._report_gen = ReportGenerator()
        self._task_gen = TaskGenerator()
        self._tj_docs: TJDocumentationService | None = None

    @property
    def tj_docs(self) -> TJDocumentationService | None:
        """The TJ documentation service instance, if set."""
        return self._tj_docs

    @tj_docs.setter
    def tj_docs(self, service: TJDocumentationService | None) -> None:
        """Set the TJ documentation service instance."""
        self._tj_docs = service

    async def execute(
        self, tool_call: ToolCall, confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Execute a tool call, dispatching to the appropriate handler.

        For write operations, requests confirmation via confirm_fn before
        persisting changes. Creates backups and validates with the compiler.

        Args:
            tool_call: The parsed tool call to execute.
            confirm_fn: Async callback to request user confirmation for writes.

        Returns:
            ToolResult with success status and content.
        """
        handler = self._get_handler(tool_call.name)
        if handler is None:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content=f"Unknown tool: {tool_call.name}",
            )

        try:
            return await handler(tool_call, confirm_fn)
        except PathSecurityError as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content=str(e),
            )
        except Exception as e:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content=f"Tool execution error: {e}",
            )

    def validate_path(self, path: str) -> Path:
        """Validate and resolve a path within the project boundary.

        Args:
            path: The file path to validate (relative or absolute).

        Returns:
            The resolved canonical absolute path.

        Raises:
            PathSecurityError: If the path is outside the project boundary.
        """
        return validate_project_path(path, self._project_dir)

    def create_backup(self, file_path: Path) -> Path:
        """Create a .bak copy of a file before modification.

        Args:
            file_path: The file to back up.

        Returns:
            Path to the created backup file.
        """
        backup_path = file_path.with_suffix(file_path.suffix + ".bak")
        shutil.copy2(file_path, backup_path)
        return backup_path

    async def validate_with_compiler(self, project_file: Path) -> CompilerResult:
        """Run the tj3 compiler against the project file.

        Args:
            project_file: Path to the main .tjp project file.

        Returns:
            CompilerResult with success status and output.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "tj3", str(project_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._project_dir),
            )
            stdout_bytes, stderr_bytes = await process.communicate()
            return CompilerResult(
                success=process.returncode == 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
            )
        except FileNotFoundError:
            return CompilerResult(
                success=False,
                stdout="",
                stderr="tj3 compiler not found. Ensure TaskJuggler is installed.",
            )

    def _get_handler(
        self, tool_name: str
    ) -> Callable[[ToolCall, ConfirmFn], Awaitable[ToolResult]] | None:
        """Look up the handler method for a tool name."""
        handlers: dict[str, Callable[[ToolCall, ConfirmFn], Awaitable[ToolResult]]] = {
            "read_file": self._handle_read_file,
            "list_files": self._handle_list_files,
            "list_tasks": self._handle_list_tasks,
            "list_resources": self._handle_list_resources,
            "find_task": self._handle_find_task,
            "find_resource": self._handle_find_resource,
            "write_file": self._handle_write_file,
            "update_task": self._handle_update_task,
            "add_task": self._handle_add_task,
            "update_resource": self._handle_update_resource,
            "write_timesheet": self._handle_write_timesheet,
            "write_journal": self._handle_write_journal,
            "write_report": self._handle_write_report,
            "compile_project": self._handle_compile_project,
            "search_tj_docs": self._handle_search_tj_docs,
        }
        return handlers.get(tool_name)

    # --- Read-only tool handlers ---

    async def _handle_read_file(
        self, tool_call: ToolCall, _confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Read a project file and return its content."""
        path_str = tool_call.arguments.get("path", "")
        resolved = self.validate_path(path_str)
        if not resolved.exists():
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content=f"File not found: {path_str}",
            )
        content = resolved.read_text(encoding="utf-8")
        return ToolResult(
            tool_call_id=tool_call.id,
            success=True,
            content=content,
        )

    async def _handle_list_files(
        self, tool_call: ToolCall, _confirm_fn: ConfirmFn
    ) -> ToolResult:
        """List files in the project directory or a subdirectory."""
        subdirectory = tool_call.arguments.get("subdirectory", "")
        if subdirectory:
            resolved = self.validate_path(subdirectory)
        else:
            resolved = self._project_dir

        if not resolved.exists():
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content=f"Directory not found: {subdirectory}",
            )

        files: list[str] = []
        for path in sorted(resolved.rglob("*")):
            if path.is_file() and not path.name.startswith("."):
                relative = path.relative_to(self._project_dir)
                files.append(str(relative).replace("\\", "/"))

        return ToolResult(
            tool_call_id=tool_call.id,
            success=True,
            content="\n".join(files) if files else "No files found.",
        )

    async def _handle_list_tasks(
        self, tool_call: ToolCall, _confirm_fn: ConfirmFn
    ) -> ToolResult:
        """List all tasks from the project."""
        tasks = self._reader.list_tasks()
        if not tasks:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=True,
                content="No tasks found in project.",
            )
        lines = []
        for t in tasks:
            parts = [f"{t.path}: {t.name}"]
            if t.effort:
                parts.append(f"effort={t.effort}")
            if t.allocations:
                parts.append(f"allocate={','.join(t.allocations)}")
            lines.append(" | ".join(parts))
        return ToolResult(
            tool_call_id=tool_call.id,
            success=True,
            content="\n".join(lines),
        )

    async def _handle_list_resources(
        self, tool_call: ToolCall, _confirm_fn: ConfirmFn
    ) -> ToolResult:
        """List all resources from the project."""
        resources = self._reader.list_resources()
        if not resources:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=True,
                content="No resources found in project.",
            )
        lines = []
        for r in resources:
            parts = [f"{r.id}: {r.name}"]
            if r.rate is not None:
                parts.append(f"rate={r.rate}")
            lines.append(" | ".join(parts))
        return ToolResult(
            tool_call_id=tool_call.id,
            success=True,
            content="\n".join(lines),
        )

    async def _handle_find_task(
        self, tool_call: ToolCall, _confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Find tasks matching a query."""
        query = tool_call.arguments.get("query", "")
        if not query:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Missing required parameter: query",
            )
        matches = self._reader.find_task(query)
        if not matches:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=True,
                content=f"No tasks found matching '{query}'.",
            )
        lines = [
            f"{m.task.path}: {m.task.name} (score={m.score:.2f})"
            for m in matches
        ]
        return ToolResult(
            tool_call_id=tool_call.id,
            success=True,
            content="\n".join(lines),
        )

    async def _handle_find_resource(
        self, tool_call: ToolCall, _confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Find resources matching a query."""
        query = tool_call.arguments.get("query", "")
        if not query:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Missing required parameter: query",
            )
        matches = self._reader.find_resource(query)
        if not matches:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=True,
                content=f"No resources found matching '{query}'.",
            )
        lines = []
        for m in matches:
            prefix = "[exact] " if m.exact else ""
            lines.append(f"{prefix}{m.resource.id}: {m.resource.name}")
        return ToolResult(
            tool_call_id=tool_call.id,
            success=True,
            content="\n".join(lines),
        )

    async def _handle_search_tj_docs(
        self, tool_call: ToolCall, _confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Search bundled TaskJuggler documentation."""
        query = tool_call.arguments.get("query", "")
        if not query:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Missing required parameter: query",
            )
        if self._tj_docs is None or not self._tj_docs.is_available:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="TaskJuggler documentation is not available.",
            )
        results = self._tj_docs.search(query)
        if not results:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=True,
                content=f"No documentation found matching '{query}'.",
            )
        sections = []
        for doc in results:
            sections.append(f"## {doc.title} (relevance: {doc.relevance_score:.2f})\n{doc.content}")
        return ToolResult(
            tool_call_id=tool_call.id,
            success=True,
            content="\n\n---\n\n".join(sections),
        )

    async def _handle_compile_project(
        self, tool_call: ToolCall, _confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Run the tj3 compiler against the project."""
        project_file = self._project_dir / self._settings.project_file
        if not project_file.exists():
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content=f"Project file not found: {self._settings.project_file}",
            )
        result = await self.validate_with_compiler(project_file)
        if result.success:
            content = "Compilation successful."
            if result.stdout.strip():
                content += f"\n{result.stdout.strip()}"
        else:
            content = f"Compilation failed.\n{result.stderr.strip()}"
        return ToolResult(
            tool_call_id=tool_call.id,
            success=result.success,
            content=content,
        )

    # --- Write tool handlers ---

    async def _handle_write_file(
        self, tool_call: ToolCall, confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Write content to a project file with safety checks."""
        path_str = tool_call.arguments.get("path", "")
        content = tool_call.arguments.get("content", "")
        resolved = self.validate_path(path_str)

        operation = "modify" if resolved.exists() else "create"
        summary = f"{operation.capitalize()} file: {path_str}"

        confirmed = await confirm_fn(summary)
        if not confirmed:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Write operation declined by user.",
            )

        return await self._safe_write(tool_call.id, resolved, content)

    async def _handle_update_task(
        self, tool_call: ToolCall, confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Update task attributes in the project."""
        task_path = tool_call.arguments.get("task_path", "")
        attributes = tool_call.arguments.get("attributes", {})

        if not task_path:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Missing required parameter: task_path",
            )

        summary = f"Update task '{task_path}' with attributes: {json.dumps(attributes)}"
        confirmed = await confirm_fn(summary)
        if not confirmed:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Write operation declined by user.",
            )

        # Find the file containing this task
        target_file = self._find_task_file(task_path)
        if target_file is None:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content=f"Could not find file containing task '{task_path}'.",
            )

        # Read, modify, and write back
        original = target_file.read_text(encoding="utf-8")
        modified = self._apply_task_update(original, task_path, attributes)
        return await self._safe_write(tool_call.id, target_file, modified)

    async def _handle_add_task(
        self, tool_call: ToolCall, confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Add a new task definition to the project."""
        parent_path = tool_call.arguments.get("parent_path", "")
        task_data = tool_call.arguments.get("task", {})

        if not task_data:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Missing required parameter: task",
            )

        task_request = TaskRequest(**task_data)
        generated = self._task_gen.generate(task_request)

        summary = f"Add task '{task_request.task_id}' under '{parent_path or 'root'}'"
        confirmed = await confirm_fn(summary)
        if not confirmed:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Write operation declined by user.",
            )

        # Find the target file (tasks include file)
        target_file = self._find_task_file(parent_path) if parent_path else None
        if target_file is None:
            # Default to tasks.tji in project root
            target_file = self._project_dir / "tasks.tji"

        if target_file.exists():
            original = target_file.read_text(encoding="utf-8")
            modified = original.rstrip() + "\n\n" + generated + "\n"
        else:
            modified = generated + "\n"

        return await self._safe_write(tool_call.id, target_file, modified)

    async def _handle_update_resource(
        self, tool_call: ToolCall, confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Update resource attributes in the project."""
        resource_id = tool_call.arguments.get("resource_id", "")
        attributes = tool_call.arguments.get("attributes", {})

        if not resource_id:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Missing required parameter: resource_id",
            )

        summary = f"Update resource '{resource_id}' with: {json.dumps(attributes)}"
        confirmed = await confirm_fn(summary)
        if not confirmed:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Write operation declined by user.",
            )

        target_file = self._find_resource_file(resource_id)
        if target_file is None:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content=f"Could not find file containing resource '{resource_id}'.",
            )

        original = target_file.read_text(encoding="utf-8")
        modified = self._apply_resource_update(original, resource_id, attributes)
        return await self._safe_write(tool_call.id, target_file, modified)

    async def _handle_write_timesheet(
        self, tool_call: ToolCall, confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Write or merge a timesheet entry."""
        from datetime import date

        resource_id = tool_call.arguments.get("resource_id", "")
        week_str = tool_call.arguments.get("week")
        entries_data = tool_call.arguments.get("entries", [])

        if not resource_id or not entries_data:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Missing required parameters: resource_id and entries",
            )

        # Parse week start date
        if week_str:
            week_start = date.fromisoformat(week_str)
        else:
            # Default to current ISO week Monday
            today = date.today()
            week_start = today - __import__("datetime").timedelta(
                days=today.weekday()
            )

        booking = BookingRequest(
            resource_id=resource_id,
            week_start=week_start,
            entries=entries_data,
        )

        filename = self._timesheet_gen.get_filename(resource_id, week_start)
        timesheets_dir = self._project_dir / "timesheets"
        timesheets_dir.mkdir(exist_ok=True)
        target_file = timesheets_dir / filename

        summary = f"Write timesheet for {resource_id} week {week_start.isoformat()}"
        confirmed = await confirm_fn(summary)
        if not confirmed:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Write operation declined by user.",
            )

        if target_file.exists():
            existing = target_file.read_text(encoding="utf-8")
            # Merge each entry into existing
            content = existing
            for entry in booking.entries:
                content = self._timesheet_gen.merge_into_existing(content, entry)
        else:
            content = self._timesheet_gen.generate(booking)

        return await self._safe_write(tool_call.id, target_file, content)

    async def _handle_write_journal(
        self, tool_call: ToolCall, confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Write a journal entry."""
        from datetime import date as date_type

        task_path = tool_call.arguments.get("task_path")
        date_str = tool_call.arguments.get("date")
        author = tool_call.arguments.get("author", self._settings.default_author)
        headline = tool_call.arguments.get("headline", "")
        summary_text = tool_call.arguments.get("summary")

        if not headline:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Missing required parameter: headline",
            )
        if not author:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="No author specified and no default author configured.",
            )

        entry_date = (
            date_type.fromisoformat(date_str) if date_str else date_type.today()
        )

        entry = JournalEntryRequest(
            task_path=task_path,
            entry_date=entry_date,
            author=author,
            headline=headline[:120],
            summary=summary_text,
        )

        generated = self._journal_gen.generate(entry)

        summary = f"Write journal entry: '{headline[:50]}' by {author}"
        confirmed = await confirm_fn(summary)
        if not confirmed:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Write operation declined by user.",
            )

        # Determine target file
        if task_path:
            target_file = self._find_task_file(task_path)
            if target_file is None:
                target_file = self._project_dir / "includes" / "journal.tji"
        else:
            target_file = self._project_dir / "includes" / "journal.tji"

        target_file.parent.mkdir(parents=True, exist_ok=True)

        if target_file.exists():
            existing = target_file.read_text(encoding="utf-8")
            content = existing.rstrip() + "\n\n" + generated + "\n"
        else:
            content = generated + "\n"

        return await self._safe_write(tool_call.id, target_file, content)

    async def _handle_write_report(
        self, tool_call: ToolCall, confirm_fn: ConfirmFn
    ) -> ToolResult:
        """Write a report definition."""
        report_id = tool_call.arguments.get("report_id", "")
        report_type = tool_call.arguments.get("report_type", "")
        config = tool_call.arguments.get("config", {})

        if not report_id or not report_type:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Missing required parameters: report_id and report_type",
            )

        # Build ReportRequest from arguments
        report_request = ReportRequest(
            report_id=report_id,
            report_type=report_type,
            title=config.get("title", report_id),
            columns=config.get("columns", ["name", "start", "end"]),
            formats=config.get("formats", ["html"]),
            sort_order=config.get("sort_order"),
            hide_expression=config.get("hide_expression"),
            time_scale=config.get("time_scale"),
            caption=config.get("caption"),
        )

        generated = self._report_gen.generate(report_request)

        summary = f"Write report definition: '{report_id}' ({report_type})"
        confirmed = await confirm_fn(summary)
        if not confirmed:
            return ToolResult(
                tool_call_id=tool_call.id,
                success=False,
                content="Write operation declined by user.",
            )

        # Write to reports include file
        target_file = self._project_dir / "reports.tji"
        if target_file.exists():
            existing = target_file.read_text(encoding="utf-8")
            content = existing.rstrip() + "\n\n" + generated + "\n"
        else:
            content = generated + "\n"

        return await self._safe_write(tool_call.id, target_file, content)

    # --- Safe write with backup/validate/rollback ---

    async def _safe_write(
        self, tool_call_id: str, file_path: Path, content: str
    ) -> ToolResult:
        """Write content to a file with backup and compiler validation.

        Workflow: backup → write → validate → rollback on failure.

        Args:
            tool_call_id: The tool call ID for the result.
            file_path: Target file path.
            content: Content to write.

        Returns:
            ToolResult indicating success or failure.
        """
        backup_path: Path | None = None

        # Create backup if file exists
        if file_path.exists():
            backup_path = self.create_backup(file_path)

        # Write the new content
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")

        # Validate with compiler
        project_file = self._project_dir / self._settings.project_file
        if project_file.exists():
            result = await self.validate_with_compiler(project_file)
            if not result.success:
                # Rollback: restore from backup or remove new file
                if backup_path and backup_path.exists():
                    shutil.copy2(backup_path, file_path)
                    backup_path.unlink()
                elif backup_path is None:
                    # File was newly created, remove it
                    file_path.unlink(missing_ok=True)

                return ToolResult(
                    tool_call_id=tool_call_id,
                    success=False,
                    content=(
                        f"Compilation failed after write. Changes rolled back.\n"
                        f"{result.stderr.strip()}"
                    ),
                )

        return ToolResult(
            tool_call_id=tool_call_id,
            success=True,
            content=f"Successfully wrote {file_path.name}",
        )

    # --- Helper methods ---

    def _find_task_file(self, task_path: str) -> Path | None:
        """Find the .tji file containing a task definition.

        Searches all .tji files in the project for the task path.

        Args:
            task_path: Dotted task path to search for.

        Returns:
            Path to the file containing the task, or None.
        """
        # Extract the task ID (last segment of dotted path)
        task_id = task_path.split(".")[-1] if task_path else ""
        if not task_id:
            return None

        for tji_file in sorted(self._project_dir.rglob("*.tji")):
            content = tji_file.read_text(encoding="utf-8")
            if f"task {task_id}" in content:
                return tji_file
        return None

    def _find_resource_file(self, resource_id: str) -> Path | None:
        """Find the .tji file containing a resource definition.

        Args:
            resource_id: The resource ID to search for.

        Returns:
            Path to the file containing the resource, or None.
        """
        for tji_file in sorted(self._project_dir.rglob("*.tji")):
            content = tji_file.read_text(encoding="utf-8")
            if f"resource {resource_id}" in content:
                return tji_file
        return None

    def _apply_task_update(
        self, content: str, task_path: str, attributes: dict[str, Any]
    ) -> str:
        """Apply attribute updates to a task in file content.

        Simple implementation that finds the task block and updates
        or appends attribute lines.

        Args:
            content: Original file content.
            task_path: Dotted task path.
            attributes: Dict of attribute names to new values.

        Returns:
            Modified file content.
        """
        import re

        task_id = task_path.split(".")[-1]
        # Find the task block
        pattern = re.compile(
            rf'(task\s+{re.escape(task_id)}\s+"[^"]*"\s*\{{)(.*?)(\}})',
            re.DOTALL,
        )
        match = pattern.search(content)
        if not match:
            return content

        header = match.group(1)
        body = match.group(2)
        closing = match.group(3)

        # Update or add each attribute
        for attr_name, attr_value in attributes.items():
            attr_pattern = re.compile(
                rf'(\s*{re.escape(attr_name)}\s+)(.+)', re.MULTILINE
            )
            attr_match = attr_pattern.search(body)
            if attr_match:
                body = body[: attr_match.start(2)] + str(attr_value) + body[attr_match.end(2):]
            else:
                body = body.rstrip() + f"\n  {attr_name} {attr_value}\n"

        return content[: match.start()] + header + body + closing + content[match.end():]

    def _apply_resource_update(
        self, content: str, resource_id: str, attributes: dict[str, Any]
    ) -> str:
        """Apply attribute updates to a resource in file content.

        Args:
            content: Original file content.
            resource_id: The resource ID to update.
            attributes: Dict of attribute names to new values.

        Returns:
            Modified file content.
        """
        import re

        pattern = re.compile(
            rf'(resource\s+{re.escape(resource_id)}\s+"[^"]*"\s*\{{)(.*?)(\}})',
            re.DOTALL,
        )
        match = pattern.search(content)
        if not match:
            return content

        header = match.group(1)
        body = match.group(2)
        closing = match.group(3)

        for attr_name, attr_value in attributes.items():
            attr_pattern = re.compile(
                rf'(\s*{re.escape(attr_name)}\s+)(.+)', re.MULTILINE
            )
            attr_match = attr_pattern.search(body)
            if attr_match:
                body = body[: attr_match.start(2)] + str(attr_value) + body[attr_match.end(2):]
            else:
                body = body.rstrip() + f"\n  {attr_name} {attr_value}\n"

        return content[: match.start()] + header + body + closing + content[match.end():]
