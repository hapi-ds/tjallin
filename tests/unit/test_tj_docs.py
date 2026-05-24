"""Unit tests for the TJ Documentation Service."""

from pathlib import Path

import pytest

from tj_chat.tj_docs import TJDocumentationService


@pytest.fixture
def docs_dir(tmp_path: Path) -> Path:
    """Create a temporary docs directory with sample markdown files."""
    docs = tmp_path / "tj-docs"
    docs.mkdir()

    (docs / "task.md").write_text(
        "# task\n\n"
        "The `task` keyword defines a unit of work.\n\n"
        "## Syntax\n\n"
        "```tjp\n"
        'task <id> "<name>" {\n'
        "  [attributes...]\n"
        "}\n"
        "```\n\n"
        "## Attributes\n\n"
        "| Attribute | Description | Example |\n"
        "|-----------|-------------|----------|\n"
        "| `effort` | Work effort required | `effort 10d` |\n"
        "| `allocate` | Assign resources | `allocate alice` |\n"
        "| `depends` | Task dependencies | `depends !schema` |\n",
        encoding="utf-8",
    )

    (docs / "resource.md").write_text(
        "# resource\n\n"
        "The `resource` keyword defines a person or team.\n\n"
        "## Syntax\n\n"
        "```tjp\n"
        'resource <id> "<name>" {\n'
        "  [attributes...]\n"
        "}\n"
        "```\n\n"
        "## Attributes\n\n"
        "| Attribute | Description | Example |\n"
        "|-----------|-------------|----------|\n"
        "| `workinghours` | Working schedule | `workinghours mon - fri 9:00 - 17:00` |\n"
        "| `rate` | Cost rate per day | `rate 950.0` |\n",
        encoding="utf-8",
    )

    (docs / "timesheet.md").write_text(
        "# timesheet\n\n"
        "The `timesheet` keyword records actual hours worked.\n\n"
        "## Syntax\n\n"
        "```tjp\n"
        "timesheet <resource_id> <start_date> <duration> {\n"
        "  [task entries...]\n"
        "}\n"
        "```\n\n"
        "## Attributes\n\n"
        "| Attribute | Description | Example |\n"
        "|-----------|-------------|----------|\n"
        "| `work` | Hours worked | `work 32h` |\n"
        "| `status` | Status indicator | `status green \"On track\"` |\n",
        encoding="utf-8",
    )

    return docs


class TestTJDocumentationServiceInit:
    """Tests for TJDocumentationService initialization."""

    def test_loads_docs_from_valid_path(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        assert service.is_available is True

    def test_degraded_mode_when_path_missing(self, tmp_path: Path) -> None:
        service = TJDocumentationService(tmp_path / "nonexistent")
        assert service.is_available is False

    def test_degraded_mode_when_path_is_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hello")
        service = TJDocumentationService(file_path)
        assert service.is_available is False

    def test_degraded_mode_when_no_md_files(self, tmp_path: Path) -> None:
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        service = TJDocumentationService(empty_dir)
        assert service.is_available is False


class TestSearch:
    """Tests for TJDocumentationService.search()."""

    def test_search_by_title(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        results = service.search("task")
        assert len(results) > 0
        assert results[0].title == "task"
        assert results[0].relevance_score == 1.0

    def test_search_case_insensitive(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        results = service.search("RESOURCE")
        assert len(results) > 0
        assert any(r.title == "resource" for r in results)

    def test_search_multiple_terms(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        results = service.search("task effort")
        # "task" section matches: "task" in title (1.0) + "effort" in content (0.8) = 0.9
        assert len(results) > 0
        assert results[0].title == "task"
        assert results[0].relevance_score == pytest.approx(0.9)

    def test_search_partial_match_scores_lower(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        results = service.search("task nonexistentterm")
        # Only "task" term matches (title match = 1.0), so score = 1.0/2 = 0.5
        matching = [r for r in results if r.title == "task"]
        assert len(matching) == 1
        assert matching[0].relevance_score == 0.5

    def test_search_no_match(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        results = service.search("xyznonexistent")
        assert results == []

    def test_search_empty_query(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        results = service.search("")
        assert results == []

    def test_search_whitespace_only(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        results = service.search("   ")
        assert results == []

    def test_search_results_ordered_by_relevance(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        results = service.search("resource workinghours")
        # resource section matches both terms (title + content)
        # other sections may match "resource" in content
        assert len(results) > 0
        scores = [r.relevance_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_search_in_degraded_mode_returns_empty(self, tmp_path: Path) -> None:
        service = TJDocumentationService(tmp_path / "nonexistent")
        results = service.search("task")
        assert results == []


class TestGetSyntaxReference:
    """Tests for TJDocumentationService.get_syntax_reference()."""

    def test_returns_nonempty_when_available(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        ref = service.get_syntax_reference()
        assert ref != ""
        assert "TaskJuggler Syntax Reference" in ref

    def test_contains_key_constructs(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        ref = service.get_syntax_reference()
        # Should contain sections for the constructs present in docs
        assert "## task" in ref
        assert "## resource" in ref
        assert "## timesheet" in ref

    def test_contains_syntax_blocks(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        ref = service.get_syntax_reference()
        assert "```tjp" in ref

    def test_returns_empty_in_degraded_mode(self, tmp_path: Path) -> None:
        service = TJDocumentationService(tmp_path / "nonexistent")
        ref = service.get_syntax_reference()
        assert ref == ""


class TestIsAvailable:
    """Tests for TJDocumentationService.is_available property."""

    def test_true_when_docs_loaded(self, docs_dir: Path) -> None:
        service = TJDocumentationService(docs_dir)
        assert service.is_available is True

    def test_false_when_path_missing(self, tmp_path: Path) -> None:
        service = TJDocumentationService(tmp_path / "missing")
        assert service.is_available is False
