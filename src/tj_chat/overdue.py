"""Overdue task detection and proactive session guidance.

Provides functions to detect overdue tasks, find upcoming milestones,
and generate session-start summaries for proactive project management.
"""

from __future__ import annotations

from datetime import date, timedelta

from tj_chat.models import OverdueTask, ProjectSummary, TaskInfo


def detect_overdue_tasks(
    tasks: list[TaskInfo], now_date: date
) -> list[OverdueTask]:
    """Find tasks that are past their planned end date without 100% completion.

    A task is considered overdue if:
    - It has a planned end_date
    - The end_date is before now_date
    - It does not have complete == 100

    Args:
        tasks: List of parsed task information from the project.
        now_date: The project's configured 'now' date for deadline calculations.

    Returns:
        List of OverdueTask objects sorted by days_overdue descending.
    """
    overdue: list[OverdueTask] = []
    for task in tasks:
        if task.end_date is None:
            continue
        try:
            end = date.fromisoformat(task.end_date)
        except ValueError:
            continue
        if end >= now_date:
            continue
        if task.complete == 100:
            continue
        days = (now_date - end).days
        overdue.append(OverdueTask(task=task, days_overdue=days))

    # Sort by most overdue first
    overdue.sort(key=lambda o: o.days_overdue, reverse=True)
    return overdue


def get_upcoming_milestones(
    tasks: list[TaskInfo], now_date: date, days: int = 14
) -> list[TaskInfo]:
    """Find milestones due within the next N days.

    Args:
        tasks: List of parsed task information from the project.
        now_date: The project's configured 'now' date.
        days: Number of days to look ahead (default 14).

    Returns:
        List of milestone TaskInfo objects due within the window,
        sorted by end_date ascending.
    """
    horizon = now_date + timedelta(days=days)
    milestones: list[tuple[date, TaskInfo]] = []

    for task in tasks:
        if not task.is_milestone:
            continue
        if task.end_date is None:
            continue
        try:
            end = date.fromisoformat(task.end_date)
        except ValueError:
            continue
        if now_date <= end <= horizon:
            milestones.append((end, task))

    milestones.sort(key=lambda m: m[0])
    return [m[1] for m in milestones]


def get_session_summary(
    project_summary: ProjectSummary,
    tasks: list[TaskInfo],
    now_date: date,
) -> str:
    """Build a text summary for session start with proactive guidance.

    Includes:
    - Overdue tasks with days overdue
    - Upcoming milestones within 14 days
    - Missing timesheets note (based on resource IDs with allocated tasks)

    Args:
        project_summary: Summary of the project structure.
        tasks: List of parsed task information from the project.
        now_date: The project's configured 'now' date.

    Returns:
        Formatted text summary string for display at session start.
    """
    sections: list[str] = []

    # Header
    sections.append(
        f"Project: {project_summary.project_name} (as of {now_date.isoformat()})"
    )

    # Overdue tasks
    overdue = detect_overdue_tasks(tasks, now_date)
    if overdue:
        lines = [f"\nOverdue tasks ({len(overdue)}):"]
        for item in overdue:
            lines.append(
                f"  - {item.task.name} ({item.task.path}): "
                f"{item.days_overdue} days overdue"
            )
        sections.append("\n".join(lines))
    else:
        sections.append("\nNo overdue tasks.")

    # Upcoming milestones
    milestones = get_upcoming_milestones(tasks, now_date)
    if milestones:
        lines = [f"\nUpcoming milestones (next 14 days):"]
        for ms in milestones:
            lines.append(f"  - {ms.name} ({ms.path}): due {ms.end_date}")
        sections.append("\n".join(lines))
    else:
        sections.append("\nNo milestones due in the next 14 days.")

    # Missing timesheets hint
    # Identify resources with allocated tasks
    allocated_resources = set()
    for task in tasks:
        for alloc in task.allocations:
            allocated_resources.add(alloc)

    if allocated_resources:
        sections.append(
            f"\nResources with allocations: {', '.join(sorted(allocated_resources))}. "
            "Check if timesheets are submitted for the current/previous week."
        )

    return "\n".join(sections)
