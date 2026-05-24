"""TaskJuggler syntax generators.

Generates valid TaskJuggler definitions for tasks, timesheets,
journal entries, and reports from structured request models.
"""

from __future__ import annotations

import re
from datetime import date

from tj_chat.models import (
    BookingRequest,
    JournalEntryRequest,
    ReportRequest,
    TaskEntry,
    TaskRequest,
)


class TaskGenerator:
    """Generates valid TaskJuggler task definitions.

    Produces a task block with ID, name, effort, allocation, and optional
    dependencies and priority attributes.
    """

    def generate(self, task: TaskRequest) -> str:
        """Generate a TaskJuggler task definition from a TaskRequest.

        Args:
            task: The task request containing ID, name, effort, allocation,
                  and optional depends/priority fields.

        Returns:
            A string containing a valid TaskJuggler task definition block.
        """
        lines: list[str] = []
        lines.append(f'task {task.task_id} "{task.name}" {{')
        lines.append(f"  effort {task.effort}")

        # Handle single or multiple allocations
        if isinstance(task.allocation, list):
            for resource_id in task.allocation:
                lines.append(f"  allocate {resource_id}")
        else:
            lines.append(f"  allocate {task.allocation}")

        # Optional dependencies
        if task.depends:
            deps_str = ", ".join(task.depends)
            lines.append(f"  depends {deps_str}")

        # Optional priority
        if task.priority is not None:
            lines.append(f"  priority {task.priority}")

        lines.append("}")
        return "\n".join(lines)


class JournalEntryGenerator:
    """Generates valid TaskJuggler journal entry statements.

    Produces syntactically correct `journalentry` blocks from structured
    request data, including date (YYYY-MM-DD), author, headline (≤120 chars),
    and optional summary.
    """

    def generate(self, entry: JournalEntryRequest) -> str:
        """Generate a valid TaskJuggler journalentry statement.

        Args:
            entry: The journal entry request containing date, author,
                headline, and optional summary.

        Returns:
            A string containing the complete journalentry block in valid
            TaskJuggler syntax.
        """
        date_str = entry.entry_date.isoformat()
        headline = self._escape_quotes(entry.headline)

        lines: list[str] = []
        lines.append(f'journalentry {date_str} "{headline}" {{')
        lines.append(f"  author {entry.author}")

        if entry.summary is not None:
            summary_text = self._escape_quotes(entry.summary)
            lines.append(f'  summary "{summary_text}"')

        lines.append("}")

        return "\n".join(lines)

    def _escape_quotes(self, text: str) -> str:
        """Escape double quotes within a string for TaskJuggler syntax.

        Args:
            text: The text to escape.

        Returns:
            The text with double quotes escaped.
        """
        return text.replace('"', '\\"')


class TimesheetGenerator:
    """Generates valid TaskJuggler timesheet blocks.

    Produces correctly formatted timesheet syntax from BookingRequest models,
    and supports merging new entries into existing timesheet files.
    """

    def generate(self, booking: BookingRequest) -> str:
        """Generate a complete timesheet block from a BookingRequest.

        Args:
            booking: The booking request containing resource, week, and task entries.

        Returns:
            A valid TaskJuggler timesheet block as a string.
        """
        week_start_str = booking.week_start.strftime("%Y-%m-%d")
        lines: list[str] = []
        lines.append(f"timesheet {booking.resource_id} {week_start_str} +1w {{")

        for entry in booking.entries:
            lines.append(self._format_task_block(entry))

        lines.append("}")
        return "\n".join(lines) + "\n"

    def merge_into_existing(self, existing: str, new_entry: TaskEntry) -> str:
        """Merge a new task entry into an existing timesheet file.

        Replaces any existing entry for the same task path with the new entry.
        Preserves all entries for other task paths.

        Args:
            existing: The existing timesheet file content.
            new_entry: The new task entry to merge.

        Returns:
            The merged timesheet content.
        """
        task_blocks = self._parse_task_blocks(existing)

        # Replace or add the new entry
        replaced = False
        for i, (task_path, _block) in enumerate(task_blocks):
            if task_path == new_entry.task_path:
                task_blocks[i] = (new_entry.task_path, self._format_task_block(new_entry))
                replaced = True
                break

        if not replaced:
            task_blocks.append((new_entry.task_path, self._format_task_block(new_entry)))

        return self._reconstruct_timesheet(existing, task_blocks)

    def get_filename(self, resource_id: str, week_start: date) -> str:
        """Generate the timesheet filename for a resource and week.

        Args:
            resource_id: The resource identifier.
            week_start: The Monday of the ISO week.

        Returns:
            Filename matching pattern YYYY-Www-<resource_id>.tji
        """
        iso_year, iso_week, _ = week_start.isocalendar()
        return f"{iso_year}-W{iso_week:02d}-{resource_id}.tji"

    def _format_hours(self, hours: float) -> str:
        """Format hours value, using integer format when possible."""
        if hours == int(hours):
            return str(int(hours))
        return str(hours)

    def _format_status(self, entry: TaskEntry) -> str | None:
        """Format the status line for a task entry, if status is present.

        Returns:
            The formatted status line(s) with proper indentation, or None.
        """
        if entry.status_color is None or entry.status_headline is None:
            return None

        if entry.status_summary:
            return (
                f'    status {entry.status_color} "{entry.status_headline}" {{\n'
                f'      summary "{entry.status_summary}"\n'
                f"    }}"
            )
        return f'    status {entry.status_color} "{entry.status_headline}"'

    def _format_task_block(self, entry: TaskEntry) -> str:
        """Format a single task entry block.

        Returns:
            The indented task block content.
        """
        lines: list[str] = []
        lines.append(f"  task {entry.task_path} {{")
        lines.append(f"    work {self._format_hours(entry.hours)}h")
        status_line = self._format_status(entry)
        if status_line:
            lines.append(status_line)
        lines.append("  }")
        return "\n".join(lines)

    def _parse_task_blocks(self, content: str) -> list[tuple[str, str]]:
        """Parse task blocks from existing timesheet content.

        Returns:
            List of (task_path, block_text) tuples.
        """
        blocks: list[tuple[str, str]] = []
        # Match task blocks: "  task <path> {" ... "  }"
        # Uses a non-greedy match that handles nested braces in status blocks
        pattern = re.compile(
            r"(  task\s+(\S+)\s*\{.*?\n  \})", re.MULTILINE | re.DOTALL
        )

        for match in pattern.finditer(content):
            task_path = match.group(2)
            block_text = match.group(1)
            blocks.append((task_path, block_text))

        return blocks

    def _reconstruct_timesheet(
        self, existing: str, task_blocks: list[tuple[str, str]]
    ) -> str:
        """Reconstruct a timesheet from its header and task blocks.

        Preserves the original timesheet header line (resource, date, duration).
        """
        header_match = re.match(r"(timesheet\s+\S+\s+\S+\s+\S+\s*\{)", existing)
        if not header_match:
            return existing

        header = header_match.group(1)
        lines: list[str] = [header]

        for _task_path, block_text in task_blocks:
            lines.append(block_text)

        lines.append("}")
        return "\n".join(lines) + "\n"


class ReportGenerator:
    """Generates valid TaskJuggler report definitions.

    Produces syntactically correct report blocks including type, ID, title,
    columns, formats, sort order, hide expressions, and time scales.
    """

    def generate(self, report: ReportRequest) -> str:
        """Generate a TaskJuggler report definition from a ReportRequest.

        Args:
            report: The report request containing type, ID, title, columns,
                formats, and optional attributes (sort_order, hide_expression,
                time_scale, caption).

        Returns:
            A string containing a valid TaskJuggler report definition block.
        """
        lines: list[str] = []

        # Opening line: <report_type> <id> "<title>" {
        lines.append(f'{report.report_type.value} {report.report_id} "{report.title}" {{')

        # formats
        formats_str = ", ".join(report.formats)
        lines.append(f"  formats {formats_str}")

        # columns
        columns_str = ", ".join(report.columns)
        lines.append(f"  columns {columns_str}")

        # Optional: sorttasks
        if report.sort_order is not None:
            lines.append(f"  sorttasks {report.sort_order}")

        # Optional: hidetask
        if report.hide_expression is not None:
            lines.append(f"  hidetask {report.hide_expression}")

        # Optional: timescale
        if report.time_scale is not None:
            lines.append(f"  timescale {report.time_scale}")

        # Optional: caption
        if report.caption is not None:
            lines.append(f'  caption "{report.caption}"')

        # Closing brace
        lines.append("}")

        return "\n".join(lines)
