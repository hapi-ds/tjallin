"""Unit tests for TaskGenerator.

Tests that TaskGenerator produces valid TaskJuggler task definitions
with the correct structure and attributes.
"""

from __future__ import annotations

from tj_chat.generators import TaskGenerator
from tj_chat.models import TaskRequest


class TestTaskGenerator:
    """Tests for TaskGenerator.generate()."""

    def setup_method(self) -> None:
        self.generator = TaskGenerator()

    def test_basic_task_with_single_allocation(self) -> None:
        """A minimal task has ID, name, effort, and allocate."""
        request = TaskRequest(
            task_id="schema",
            name="Database Schema",
            effort="5d",
            allocation="alice",
        )
        result = self.generator.generate(request)

        assert 'task schema "Database Schema" {' in result
        assert "  effort 5d" in result
        assert "  allocate alice" in result
        assert result.endswith("}")

    def test_task_with_multiple_allocations(self) -> None:
        """Multiple allocations produce separate allocate lines."""
        request = TaskRequest(
            task_id="endpoints",
            name="REST Endpoints",
            effort="15d",
            allocation=["alice", "bob"],
        )
        result = self.generator.generate(request)

        assert 'task endpoints "REST Endpoints" {' in result
        assert "  allocate alice" in result
        assert "  allocate bob" in result

    def test_task_with_dependencies(self) -> None:
        """Dependencies are rendered as a comma-separated depends line."""
        request = TaskRequest(
            task_id="integration",
            name="API Integration",
            effort="10d",
            allocation="bob",
            depends=["!components", "development.backend_api.endpoints"],
        )
        result = self.generator.generate(request)

        assert "  depends !components, development.backend_api.endpoints" in result

    def test_task_with_priority(self) -> None:
        """Priority is rendered when specified."""
        request = TaskRequest(
            task_id="critical_fix",
            name="Critical Bug Fix",
            effort="2d",
            allocation="alice",
            priority=900,
        )
        result = self.generator.generate(request)

        assert "  priority 900" in result

    def test_task_with_all_optional_fields(self) -> None:
        """A task with all fields produces the complete block."""
        request = TaskRequest(
            task_id="deploy",
            name="Deploy to Production",
            effort="1d",
            allocation=["alice", "bob"],
            depends=["!testing", "!review"],
            priority=800,
        )
        result = self.generator.generate(request)

        lines = result.split("\n")
        assert lines[0] == 'task deploy "Deploy to Production" {'
        assert "  effort 1d" in result
        assert "  allocate alice" in result
        assert "  allocate bob" in result
        assert "  depends !testing, !review" in result
        assert "  priority 800" in result
        assert lines[-1] == "}"

    def test_task_without_optional_fields(self) -> None:
        """A task without depends or priority omits those lines."""
        request = TaskRequest(
            task_id="docs",
            name="Write Documentation",
            effort="3d",
            allocation="carol",
        )
        result = self.generator.generate(request)

        assert "depends" not in result
        assert "priority" not in result

    def test_effort_with_hours(self) -> None:
        """Effort can be specified in hours."""
        request = TaskRequest(
            task_id="meeting",
            name="Sprint Planning",
            effort="4h",
            allocation="alice",
        )
        result = self.generator.generate(request)

        assert "  effort 4h" in result

    def test_task_name_with_special_characters(self) -> None:
        """Task names with special characters are properly quoted."""
        request = TaskRequest(
            task_id="phase_2",
            name="Phase 2: Development & Testing",
            effort="20d",
            allocation="alice",
        )
        result = self.generator.generate(request)

        assert 'task phase_2 "Phase 2: Development & Testing" {' in result
