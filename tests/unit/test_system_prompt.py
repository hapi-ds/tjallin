"""Unit tests for the system prompt builder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from tj_chat.models import ProjectSummary
from tj_chat.system_prompt import (
    INCLUDE_FILE_DESCRIPTIONS,
    TOOL_NAMES,
    build_system_prompt,
)


@pytest.fixture
def sample_summary() -> ProjectSummary:
    """Create a sample ProjectSummary for testing."""
    return ProjectSummary(
        project_name="Acme Project",
        start_date="2024-01-01",
        end_date="+26w",
        now_date="2024-06-01",
        file_tree=["project.tjp", "includes/tasks.tji", "includes/resources.tji"],
        resource_ids=["alice", "bob", "charlie"],
        top_level_tasks=["Development", "Testing", "Deployment"],
    )


class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    def test_contains_role_description(self, sample_summary: ProjectSummary) -> None:
        """System prompt starts with role description."""
        result = build_system_prompt(sample_summary)
        assert "TaskJuggler project assistant" in result

    def test_contains_project_name(self, sample_summary: ProjectSummary) -> None:
        """System prompt includes the project name."""
        result = build_system_prompt(sample_summary)
        assert "Acme Project" in result

    def test_contains_project_dates(self, sample_summary: ProjectSummary) -> None:
        """System prompt includes project start, end, and now dates."""
        result = build_system_prompt(sample_summary)
        assert "2024-01-01" in result
        assert "+26w" in result
        assert "2024-06-01" in result

    def test_contains_all_file_tree_entries(
        self, sample_summary: ProjectSummary
    ) -> None:
        """System prompt lists all files from the project file tree."""
        result = build_system_prompt(sample_summary)
        for f in sample_summary.file_tree:
            assert f in result

    def test_contains_all_resource_ids(self, sample_summary: ProjectSummary) -> None:
        """System prompt lists all resource IDs."""
        result = build_system_prompt(sample_summary)
        for rid in sample_summary.resource_ids:
            assert rid in result

    def test_contains_all_top_level_tasks(
        self, sample_summary: ProjectSummary
    ) -> None:
        """System prompt lists all top-level tasks."""
        result = build_system_prompt(sample_summary)
        for task in sample_summary.top_level_tasks:
            assert task in result

    def test_contains_all_tool_names(self, sample_summary: ProjectSummary) -> None:
        """System prompt lists all available tool names."""
        result = build_system_prompt(sample_summary)
        for tool in TOOL_NAMES:
            assert tool in result

    def test_contains_include_file_descriptions(
        self, sample_summary: ProjectSummary
    ) -> None:
        """System prompt includes descriptions of standard include files."""
        result = build_system_prompt(sample_summary)
        for filename, description in INCLUDE_FILE_DESCRIPTIONS.items():
            assert filename in result
            assert description in result

    def test_no_syntax_section_without_docs(
        self, sample_summary: ProjectSummary
    ) -> None:
        """System prompt omits syntax section when no docs service provided."""
        result = build_system_prompt(sample_summary, tj_docs_service=None)
        assert "TaskJuggler Syntax Reference" not in result

    def test_no_syntax_section_when_docs_unavailable(
        self, sample_summary: ProjectSummary
    ) -> None:
        """System prompt omits syntax section when docs service is unavailable."""
        mock_docs = MagicMock()
        mock_docs.is_available = False
        result = build_system_prompt(sample_summary, tj_docs_service=mock_docs)
        assert "TaskJuggler Syntax Reference" not in result

    def test_includes_syntax_reference_when_docs_available(
        self, sample_summary: ProjectSummary
    ) -> None:
        """System prompt includes syntax reference when docs are available."""
        mock_docs = MagicMock()
        mock_docs.is_available = True
        mock_docs.get_syntax_reference.return_value = (
            "# TaskJuggler Syntax Reference\n\n## task\n\n```\ntask id \"name\" { }\n```"
        )
        result = build_system_prompt(sample_summary, tj_docs_service=mock_docs)
        assert "TaskJuggler Syntax Reference" in result
        assert 'task id "name"' in result

    def test_empty_syntax_reference_not_included(
        self, sample_summary: ProjectSummary
    ) -> None:
        """System prompt omits syntax section when reference is empty string."""
        mock_docs = MagicMock()
        mock_docs.is_available = True
        mock_docs.get_syntax_reference.return_value = ""
        result = build_system_prompt(sample_summary, tj_docs_service=None)
        # Should not have an extra empty section
        assert not result.endswith("\n\n")

    def test_empty_file_tree(self) -> None:
        """System prompt handles empty file tree gracefully."""
        summary = ProjectSummary(
            project_name="Empty",
            start_date="",
            end_date="",
            now_date="",
            file_tree=[],
            resource_ids=[],
            top_level_tasks=[],
        )
        result = build_system_prompt(summary)
        assert "No project files found" in result

    def test_empty_resources(self) -> None:
        """System prompt handles empty resources gracefully."""
        summary = ProjectSummary(
            project_name="Empty",
            start_date="",
            end_date="",
            now_date="",
            file_tree=[],
            resource_ids=[],
            top_level_tasks=[],
        )
        result = build_system_prompt(summary)
        assert "No resources defined" in result

    def test_empty_tasks(self) -> None:
        """System prompt handles empty tasks gracefully."""
        summary = ProjectSummary(
            project_name="Empty",
            start_date="",
            end_date="",
            now_date="",
            file_tree=[],
            resource_ids=[],
            top_level_tasks=[],
        )
        result = build_system_prompt(summary)
        assert "No tasks defined" in result

    def test_returns_string(self, sample_summary: ProjectSummary) -> None:
        """build_system_prompt returns a string."""
        result = build_system_prompt(sample_summary)
        assert isinstance(result, str)

    def test_search_tj_docs_in_tools(self) -> None:
        """search_tj_docs is listed as an available tool."""
        assert "search_tj_docs" in TOOL_NAMES

    def test_with_real_tj_docs_service(
        self, sample_summary: ProjectSummary, tmp_path: Path
    ) -> None:
        """System prompt works with a real TJDocumentationService instance."""
        from tj_chat.tj_docs import TJDocumentationService

        # Create a minimal docs directory with one file
        docs_dir = tmp_path / "tj-docs"
        docs_dir.mkdir()
        (docs_dir / "task.md").write_text(
            "# task\n\n```\ntask id \"name\" { }\n```\n\n"
            "| Attribute | Description |\n"
            "| --- | --- |\n"
            "| effort | Work effort |\n",
            encoding="utf-8",
        )

        service = TJDocumentationService(docs_dir)
        result = build_system_prompt(sample_summary, tj_docs_service=service)
        assert "TaskJuggler Syntax Reference" in result
        assert "task" in result
