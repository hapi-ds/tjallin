"""System prompt builder for the LLM Agent Chat service.

Constructs the system prompt that provides the LLM with project context,
available tools, include file descriptions, and TaskJuggler syntax reference.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tj_chat.models import ProjectSummary

if TYPE_CHECKING:
    from tj_chat.tj_docs import TJDocumentationService

# All tools available to the LLM agent
TOOL_NAMES: list[str] = [
    "read_file",
    "list_files",
    "list_tasks",
    "list_resources",
    "find_task",
    "find_resource",
    "write_file",
    "update_task",
    "add_task",
    "update_resource",
    "write_timesheet",
    "write_journal",
    "write_report",
    "compile_project",
    "search_tj_docs",
]

# Descriptions of standard TaskJuggler include files
INCLUDE_FILE_DESCRIPTIONS: dict[str, str] = {
    "tasks.tji": "Task definitions including hierarchy, effort, allocations, and dependencies",
    "resources.tji": "Resource definitions including team members, rates, and working hours",
    "reports.tji": "Report definitions for Gantt charts, resource reports, and status reports",
    "accounts.tji": "Account definitions for cost tracking and budget management",
}


def build_system_prompt(
    project_summary: ProjectSummary,
    tj_docs_service: TJDocumentationService | None = None,
) -> str:
    """Build the system prompt for the LLM agent.

    Assembles a comprehensive system prompt containing the role description,
    project structure, available tools, include file descriptions, and
    optionally a condensed TaskJuggler syntax reference.

    Args:
        project_summary: Summary of the project structure including file tree,
            resource IDs, and top-level tasks.
        tj_docs_service: Optional TJ documentation service for including
            syntax reference. If None or unavailable, the syntax section
            is omitted.

    Returns:
        The complete system prompt string.
    """
    sections: list[str] = []

    # 1. Role description
    sections.append(_build_role_section(project_summary))

    # 2. Project file tree
    sections.append(_build_file_tree_section(project_summary.file_tree))

    # 3. Resource IDs
    sections.append(_build_resources_section(project_summary.resource_ids))

    # 4. Top-level tasks
    sections.append(_build_tasks_section(project_summary.top_level_tasks))

    # 5. Available tools
    sections.append(_build_tools_section())

    # 6. Include file descriptions
    sections.append(_build_include_files_section())

    # 7. Condensed TJ syntax reference (when available)
    syntax_section = _build_syntax_section(tj_docs_service)
    if syntax_section:
        sections.append(syntax_section)

    return "\n\n".join(sections)


def _build_role_section(project_summary: ProjectSummary) -> str:
    """Build the role description section."""
    lines = [
        "You are a TaskJuggler project assistant.",
        "You help manage project plans by reading and writing TaskJuggler "
        "(.tjp and .tji) files.",
        "You can review project status, update tasks and resources, "
        "write timesheets, create journal entries, and generate reports.",
        "Always validate changes with the compiler before persisting them.",
    ]
    if project_summary.project_name:
        lines.append(f"Current project: {project_summary.project_name}")
    if project_summary.start_date:
        lines.append(f"Project start: {project_summary.start_date}")
    if project_summary.end_date:
        lines.append(f"Project end: {project_summary.end_date}")
    if project_summary.now_date:
        lines.append(f"Project now date: {project_summary.now_date}")
    return "\n".join(lines)


def _build_file_tree_section(file_tree: list[str]) -> str:
    """Build the project file tree section."""
    lines = ["## Project Files"]
    if file_tree:
        for f in file_tree:
            lines.append(f"- {f}")
    else:
        lines.append("No project files found.")
    return "\n".join(lines)


def _build_resources_section(resource_ids: list[str]) -> str:
    """Build the resource IDs section."""
    lines = ["## Resources"]
    if resource_ids:
        for rid in resource_ids:
            lines.append(f"- {rid}")
    else:
        lines.append("No resources defined.")
    return "\n".join(lines)


def _build_tasks_section(top_level_tasks: list[str]) -> str:
    """Build the top-level tasks section."""
    lines = ["## Top-Level Tasks"]
    if top_level_tasks:
        for task in top_level_tasks:
            lines.append(f"- {task}")
    else:
        lines.append("No tasks defined.")
    return "\n".join(lines)


def _build_tools_section() -> str:
    """Build the available tools section."""
    lines = ["## Available Tools"]
    for tool in TOOL_NAMES:
        lines.append(f"- {tool}")
    return "\n".join(lines)


def _build_include_files_section() -> str:
    """Build the include file descriptions section."""
    lines = ["## Include Files"]
    for filename, description in INCLUDE_FILE_DESCRIPTIONS.items():
        lines.append(f"- **{filename}**: {description}")
    return "\n".join(lines)


def _build_syntax_section(
    tj_docs_service: TJDocumentationService | None,
) -> str:
    """Build the TJ syntax reference section.

    Returns the condensed syntax reference from the documentation service,
    or an empty string if documentation is unavailable.

    Args:
        tj_docs_service: Optional documentation service instance.

    Returns:
        Syntax reference string, or empty string if unavailable.
    """
    if tj_docs_service is None:
        return ""
    if not tj_docs_service.is_available:
        return ""
    return tj_docs_service.get_syntax_reference()
