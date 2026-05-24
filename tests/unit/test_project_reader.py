"""Unit tests for the ProjectReader class."""

from pathlib import Path

import pytest

from tj_chat.project_reader import ProjectReader


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a minimal project directory with sample TJ files."""
    # Create main project file
    tjp_content = """\
project acme_web "Acme Web Platform" 2024-01-15 +26w {
  timezone "Europe/Stockholm"
  timeformat "%Y-%m-%d"
  now 2024-02-05
}

include "includes/resources.tji"
include "includes/tasks.tji"
"""
    (tmp_path / "project.tjp").write_text(tjp_content, encoding="utf-8")

    # Create includes directory
    includes = tmp_path / "includes"
    includes.mkdir()

    # Create resources file
    resources_content = """\
resource alice "Alice" {
  workinghours mon - fri 9:00 - 17:00
  rate 950.0
}

resource bob "Bob" {
  workinghours mon - fri 9:00 - 17:00
  rate 800.0
}
"""
    (includes / "resources.tji").write_text(resources_content, encoding="utf-8")

    # Create tasks file
    tasks_content = """\
task acme "Acme Web Platform" {
  task planning "Phase 1: Planning" {
    task requirements "Requirements Gathering" {
      effort 5d
      allocate alice
    }
    task architecture "Architecture Design" {
      effort 5d
      allocate alice
      depends !requirements
    }
    task planning_complete "Planning Complete" {
      milestone
      depends !requirements, !architecture
    }
  }
  task development "Phase 2: Development" {
    depends !planning.planning_complete
    task backend "Backend API" {
      effort 15d
      allocate alice
      allocate bob
    }
  }
}
"""
    (includes / "tasks.tji").write_text(tasks_content, encoding="utf-8")

    return tmp_path


@pytest.fixture
def reader(project_dir: Path) -> ProjectReader:
    """Create a ProjectReader instance for the test project."""
    return ProjectReader(project_dir)


class TestGetProjectSummary:
    """Tests for get_project_summary()."""

    def test_extracts_project_name(self, reader: ProjectReader) -> None:
        summary = reader.get_project_summary()
        assert summary.project_name == "Acme Web Platform"

    def test_extracts_start_date(self, reader: ProjectReader) -> None:
        summary = reader.get_project_summary()
        assert summary.start_date == "2024-01-15"

    def test_extracts_now_date(self, reader: ProjectReader) -> None:
        summary = reader.get_project_summary()
        assert summary.now_date == "2024-02-05"

    def test_includes_resource_ids(self, reader: ProjectReader) -> None:
        summary = reader.get_project_summary()
        assert "alice" in summary.resource_ids
        assert "bob" in summary.resource_ids

    def test_includes_top_level_tasks(self, reader: ProjectReader) -> None:
        summary = reader.get_project_summary()
        # Top-level tasks are direct children of root (path has 1 dot)
        assert "Phase 1: Planning" in summary.top_level_tasks
        assert "Phase 2: Development" in summary.top_level_tasks

    def test_includes_file_tree(self, reader: ProjectReader) -> None:
        summary = reader.get_project_summary()
        assert "project.tjp" in summary.file_tree
        assert "includes/resources.tji" in summary.file_tree
        assert "includes/tasks.tji" in summary.file_tree


class TestListTasks:
    """Tests for list_tasks()."""

    def test_finds_all_tasks(self, reader: ProjectReader) -> None:
        tasks = reader.list_tasks()
        names = [t.name for t in tasks]
        assert "Acme Web Platform" in names
        assert "Phase 1: Planning" in names
        assert "Requirements Gathering" in names
        assert "Architecture Design" in names
        assert "Planning Complete" in names
        assert "Backend API" in names

    def test_task_paths_are_dotted(self, reader: ProjectReader) -> None:
        tasks = reader.list_tasks()
        req_task = next(t for t in tasks if t.name == "Requirements Gathering")
        assert req_task.path == "acme.planning.requirements"

    def test_extracts_effort(self, reader: ProjectReader) -> None:
        tasks = reader.list_tasks()
        req_task = next(t for t in tasks if t.name == "Requirements Gathering")
        assert req_task.effort == "5d"

    def test_extracts_allocations(self, reader: ProjectReader) -> None:
        tasks = reader.list_tasks()
        backend = next(t for t in tasks if t.name == "Backend API")
        assert "alice" in backend.allocations
        assert "bob" in backend.allocations

    def test_extracts_dependencies(self, reader: ProjectReader) -> None:
        tasks = reader.list_tasks()
        arch = next(t for t in tasks if t.name == "Architecture Design")
        assert "!requirements" in arch.dependencies

    def test_identifies_milestones(self, reader: ProjectReader) -> None:
        tasks = reader.list_tasks()
        milestone = next(t for t in tasks if t.name == "Planning Complete")
        assert milestone.is_milestone is True

    def test_non_milestones_not_flagged(self, reader: ProjectReader) -> None:
        tasks = reader.list_tasks()
        req_task = next(t for t in tasks if t.name == "Requirements Gathering")
        assert req_task.is_milestone is False


class TestListResources:
    """Tests for list_resources()."""

    def test_finds_all_resources(self, reader: ProjectReader) -> None:
        resources = reader.list_resources()
        ids = [r.id for r in resources]
        assert "alice" in ids
        assert "bob" in ids

    def test_extracts_name(self, reader: ProjectReader) -> None:
        resources = reader.list_resources()
        alice = next(r for r in resources if r.id == "alice")
        assert alice.name == "Alice"

    def test_extracts_rate(self, reader: ProjectReader) -> None:
        resources = reader.list_resources()
        alice = next(r for r in resources if r.id == "alice")
        assert alice.rate == 950.0

    def test_extracts_working_hours(self, reader: ProjectReader) -> None:
        resources = reader.list_resources()
        alice = next(r for r in resources if r.id == "alice")
        assert alice.working_hours is not None
        assert "mon" in alice.working_hours


class TestFindTask:
    """Tests for find_task()."""

    def test_returns_max_5_results(self, reader: ProjectReader) -> None:
        results = reader.find_task("a")
        assert len(results) <= 5

    def test_results_ordered_by_decreasing_score(self, reader: ProjectReader) -> None:
        results = reader.find_task("planning")
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_finds_by_name(self, reader: ProjectReader) -> None:
        results = reader.find_task("Backend API")
        assert len(results) > 0
        assert results[0].task.name == "Backend API"

    def test_finds_by_path(self, reader: ProjectReader) -> None:
        results = reader.find_task("acme.planning.requirements")
        assert len(results) > 0
        assert results[0].task.path == "acme.planning.requirements"

    def test_empty_query_returns_results(self, reader: ProjectReader) -> None:
        # Empty string has 0 ratio with non-empty strings
        results = reader.find_task("")
        # SequenceMatcher("", "something") returns 0.0, so no results
        assert len(results) == 0


class TestFindResource:
    """Tests for find_resource()."""

    def test_exact_match_by_id(self, reader: ProjectReader) -> None:
        results = reader.find_resource("alice")
        assert len(results) > 0
        assert results[0].resource.id == "alice"
        assert results[0].exact is True

    def test_exact_match_by_name(self, reader: ProjectReader) -> None:
        results = reader.find_resource("Alice")
        assert len(results) > 0
        assert results[0].resource.id == "alice"
        assert results[0].exact is True

    def test_fuzzy_match(self, reader: ProjectReader) -> None:
        results = reader.find_resource("alic")
        assert len(results) > 0
        # Should find alice as closest match
        assert results[0].resource.id == "alice"

    def test_returns_max_5_results(self, reader: ProjectReader) -> None:
        results = reader.find_resource("a")
        assert len(results) <= 5


class TestGetFileTree:
    """Tests for get_file_tree()."""

    def test_lists_files(self, reader: ProjectReader) -> None:
        tree = reader.get_file_tree()
        assert "project.tjp" in tree
        assert "includes/resources.tji" in tree

    def test_uses_forward_slashes(self, reader: ProjectReader) -> None:
        tree = reader.get_file_tree()
        for path in tree:
            assert "\\" not in path

    def test_excludes_hidden_files(self, project_dir: Path, reader: ProjectReader) -> None:
        (project_dir / ".hidden").write_text("hidden", encoding="utf-8")
        tree = reader.get_file_tree()
        assert ".hidden" not in tree

    def test_empty_dir_returns_empty(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        reader = ProjectReader(empty_dir)
        assert reader.get_file_tree() == []

    def test_nonexistent_dir_returns_empty(self, tmp_path: Path) -> None:
        reader = ProjectReader(tmp_path / "nonexistent")
        assert reader.get_file_tree() == []


class TestWithRealProject:
    """Tests against the actual project files in the repository."""

    @pytest.fixture
    def real_reader(self) -> ProjectReader:
        """Create a reader pointing to the actual project directory."""
        project_path = Path(__file__).parent.parent.parent / "project"
        if not project_path.exists():
            pytest.skip("Real project directory not available")
        return ProjectReader(project_path)

    def test_real_project_summary(self, real_reader: ProjectReader) -> None:
        summary = real_reader.get_project_summary()
        assert summary.project_name == "Acme Web Platform"
        assert summary.start_date == "2024-01-15"
        assert summary.now_date == "2024-02-05"
        assert "alice" in summary.resource_ids
        assert len(summary.file_tree) > 0

    def test_real_project_tasks(self, real_reader: ProjectReader) -> None:
        tasks = real_reader.list_tasks()
        assert len(tasks) > 0
        # Should find the root task
        root = next((t for t in tasks if t.name == "Acme Web Platform"), None)
        assert root is not None
        assert root.path == "acme"

    def test_real_project_resources(self, real_reader: ProjectReader) -> None:
        resources = real_reader.list_resources()
        ids = [r.id for r in resources]
        assert "alice" in ids
        assert "bob" in ids
        assert "carol" in ids
        assert "dave" in ids
        assert "eve" in ids
