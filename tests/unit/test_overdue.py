"""Unit tests for the overdue detection and proactive guidance module."""

from datetime import date

import pytest

from tj_chat.models import OverdueTask, ProjectSummary, TaskInfo
from tj_chat.overdue import (
    detect_overdue_tasks,
    get_session_summary,
    get_upcoming_milestones,
)


@pytest.fixture
def sample_tasks() -> list[TaskInfo]:
    """Create a list of sample tasks for testing."""
    return [
        TaskInfo(
            path="acme.planning.requirements",
            name="Requirements Gathering",
            effort="5d",
            allocations=["alice"],
            end_date="2024-01-25",
            complete=100,
        ),
        TaskInfo(
            path="acme.planning.architecture",
            name="Architecture Design",
            effort="5d",
            allocations=["alice"],
            end_date="2024-01-30",
            complete=50,
        ),
        TaskInfo(
            path="acme.development.backend",
            name="Backend API",
            effort="15d",
            allocations=["alice", "bob"],
            end_date="2024-02-20",
            complete=None,
        ),
        TaskInfo(
            path="acme.planning.planning_complete",
            name="Planning Complete",
            is_milestone=True,
            end_date="2024-02-10",
        ),
        TaskInfo(
            path="acme.development.feature_complete",
            name="Feature Complete",
            is_milestone=True,
            end_date="2024-03-01",
        ),
        TaskInfo(
            path="acme.testing.release",
            name="Release Candidate",
            is_milestone=True,
            end_date="2024-04-01",
        ),
        TaskInfo(
            path="acme.no_date",
            name="No Date Task",
            effort="3d",
            allocations=["bob"],
        ),
    ]


class TestDetectOverdueTasks:
    """Tests for detect_overdue_tasks()."""

    def test_finds_overdue_incomplete_task(self, sample_tasks: list[TaskInfo]) -> None:
        now = date(2024, 2, 5)
        overdue = detect_overdue_tasks(sample_tasks, now)
        paths = [o.task.path for o in overdue]
        assert "acme.planning.architecture" in paths

    def test_excludes_completed_task(self, sample_tasks: list[TaskInfo]) -> None:
        now = date(2024, 2, 5)
        overdue = detect_overdue_tasks(sample_tasks, now)
        paths = [o.task.path for o in overdue]
        assert "acme.planning.requirements" not in paths

    def test_excludes_task_not_yet_due(self, sample_tasks: list[TaskInfo]) -> None:
        now = date(2024, 2, 5)
        overdue = detect_overdue_tasks(sample_tasks, now)
        paths = [o.task.path for o in overdue]
        assert "acme.development.backend" not in paths

    def test_excludes_task_without_end_date(self, sample_tasks: list[TaskInfo]) -> None:
        now = date(2024, 2, 5)
        overdue = detect_overdue_tasks(sample_tasks, now)
        paths = [o.task.path for o in overdue]
        assert "acme.no_date" not in paths

    def test_calculates_days_overdue_correctly(
        self, sample_tasks: list[TaskInfo]
    ) -> None:
        now = date(2024, 2, 5)
        overdue = detect_overdue_tasks(sample_tasks, now)
        arch = next(o for o in overdue if o.task.path == "acme.planning.architecture")
        # 2024-01-30 to 2024-02-05 = 6 days
        assert arch.days_overdue == 6

    def test_sorted_by_days_overdue_descending(self) -> None:
        tasks = [
            TaskInfo(
                path="a", name="A", end_date="2024-02-01", complete=0
            ),
            TaskInfo(
                path="b", name="B", end_date="2024-01-20", complete=50
            ),
            TaskInfo(
                path="c", name="C", end_date="2024-01-25", complete=None
            ),
        ]
        now = date(2024, 2, 5)
        overdue = detect_overdue_tasks(tasks, now)
        days = [o.days_overdue for o in overdue]
        assert days == sorted(days, reverse=True)

    def test_empty_tasks_returns_empty(self) -> None:
        assert detect_overdue_tasks([], date(2024, 2, 5)) == []

    def test_task_due_today_not_overdue(self) -> None:
        tasks = [
            TaskInfo(path="x", name="X", end_date="2024-02-05", complete=50)
        ]
        overdue = detect_overdue_tasks(tasks, date(2024, 2, 5))
        assert len(overdue) == 0

    def test_task_with_invalid_date_skipped(self) -> None:
        tasks = [
            TaskInfo(path="x", name="X", end_date="not-a-date", complete=50)
        ]
        overdue = detect_overdue_tasks(tasks, date(2024, 2, 5))
        assert len(overdue) == 0

    def test_task_with_none_complete_is_overdue(self) -> None:
        """A task with no completion info (None) is considered not complete."""
        tasks = [
            TaskInfo(path="x", name="X", end_date="2024-01-30", complete=None)
        ]
        overdue = detect_overdue_tasks(tasks, date(2024, 2, 5))
        assert len(overdue) == 1


class TestGetUpcomingMilestones:
    """Tests for get_upcoming_milestones()."""

    def test_finds_milestones_within_window(
        self, sample_tasks: list[TaskInfo]
    ) -> None:
        now = date(2024, 2, 5)
        milestones = get_upcoming_milestones(sample_tasks, now)
        names = [m.name for m in milestones]
        assert "Planning Complete" in names

    def test_excludes_milestones_beyond_window(
        self, sample_tasks: list[TaskInfo]
    ) -> None:
        now = date(2024, 2, 5)
        milestones = get_upcoming_milestones(sample_tasks, now)
        names = [m.name for m in milestones]
        assert "Release Candidate" not in names

    def test_excludes_non_milestones(self, sample_tasks: list[TaskInfo]) -> None:
        now = date(2024, 2, 5)
        milestones = get_upcoming_milestones(sample_tasks, now)
        names = [m.name for m in milestones]
        assert "Backend API" not in names

    def test_excludes_milestones_before_now(self) -> None:
        tasks = [
            TaskInfo(
                path="m", name="Past Milestone", is_milestone=True, end_date="2024-01-01"
            )
        ]
        milestones = get_upcoming_milestones(tasks, date(2024, 2, 5))
        assert len(milestones) == 0

    def test_includes_milestone_on_now_date(self) -> None:
        tasks = [
            TaskInfo(
                path="m", name="Today Milestone", is_milestone=True, end_date="2024-02-05"
            )
        ]
        milestones = get_upcoming_milestones(tasks, date(2024, 2, 5))
        assert len(milestones) == 1

    def test_custom_days_window(self, sample_tasks: list[TaskInfo]) -> None:
        now = date(2024, 2, 5)
        # Feature Complete is on 2024-03-01, 25 days away
        milestones = get_upcoming_milestones(sample_tasks, now, days=30)
        names = [m.name for m in milestones]
        assert "Feature Complete" in names

    def test_sorted_by_end_date_ascending(self) -> None:
        tasks = [
            TaskInfo(
                path="b", name="B", is_milestone=True, end_date="2024-02-15"
            ),
            TaskInfo(
                path="a", name="A", is_milestone=True, end_date="2024-02-08"
            ),
        ]
        milestones = get_upcoming_milestones(tasks, date(2024, 2, 5))
        assert milestones[0].name == "A"
        assert milestones[1].name == "B"

    def test_empty_tasks_returns_empty(self) -> None:
        assert get_upcoming_milestones([], date(2024, 2, 5)) == []

    def test_milestone_without_end_date_excluded(self) -> None:
        tasks = [
            TaskInfo(path="m", name="No Date", is_milestone=True, end_date=None)
        ]
        milestones = get_upcoming_milestones(tasks, date(2024, 2, 5))
        assert len(milestones) == 0


class TestGetSessionSummary:
    """Tests for get_session_summary()."""

    @pytest.fixture
    def project_summary(self) -> ProjectSummary:
        return ProjectSummary(
            project_name="Acme Web Platform",
            start_date="2024-01-15",
            end_date="+26w",
            now_date="2024-02-05",
            file_tree=["project.tjp", "includes/tasks.tji"],
            resource_ids=["alice", "bob"],
            top_level_tasks=["Planning", "Development"],
        )

    def test_includes_project_name(
        self, project_summary: ProjectSummary, sample_tasks: list[TaskInfo]
    ) -> None:
        summary = get_session_summary(project_summary, sample_tasks, date(2024, 2, 5))
        assert "Acme Web Platform" in summary

    def test_includes_now_date(
        self, project_summary: ProjectSummary, sample_tasks: list[TaskInfo]
    ) -> None:
        summary = get_session_summary(project_summary, sample_tasks, date(2024, 2, 5))
        assert "2024-02-05" in summary

    def test_includes_overdue_tasks(
        self, project_summary: ProjectSummary, sample_tasks: list[TaskInfo]
    ) -> None:
        summary = get_session_summary(project_summary, sample_tasks, date(2024, 2, 5))
        assert "Overdue tasks" in summary
        assert "Architecture Design" in summary

    def test_includes_upcoming_milestones(
        self, project_summary: ProjectSummary, sample_tasks: list[TaskInfo]
    ) -> None:
        summary = get_session_summary(project_summary, sample_tasks, date(2024, 2, 5))
        assert "Upcoming milestones" in summary
        assert "Planning Complete" in summary

    def test_includes_resource_allocation_hint(
        self, project_summary: ProjectSummary, sample_tasks: list[TaskInfo]
    ) -> None:
        summary = get_session_summary(project_summary, sample_tasks, date(2024, 2, 5))
        assert "alice" in summary
        assert "bob" in summary
        assert "timesheets" in summary

    def test_no_overdue_message(self, project_summary: ProjectSummary) -> None:
        tasks = [
            TaskInfo(
                path="x", name="X", end_date="2024-03-01", complete=50
            )
        ]
        summary = get_session_summary(project_summary, tasks, date(2024, 2, 5))
        assert "No overdue tasks" in summary

    def test_no_milestones_message(self, project_summary: ProjectSummary) -> None:
        tasks = [
            TaskInfo(path="x", name="X", effort="5d", allocations=["alice"])
        ]
        summary = get_session_summary(project_summary, tasks, date(2024, 2, 5))
        assert "No milestones due" in summary
