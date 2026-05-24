"""Unit tests for the JournalEntryGenerator class."""

from __future__ import annotations

from datetime import date

from tj_chat.generators import JournalEntryGenerator
from tj_chat.models import JournalEntryRequest


class TestJournalEntryGenerator:
    """Tests for JournalEntryGenerator.generate()."""

    def setup_method(self) -> None:
        self.generator = JournalEntryGenerator()

    def test_basic_entry_without_summary(self) -> None:
        """Generate a minimal journal entry with only required fields."""
        entry = JournalEntryRequest(
            entry_date=date(2024, 2, 1),
            author="eve",
            headline="Project kickoff completed",
        )
        result = self.generator.generate(entry)

        assert 'journalentry 2024-02-01 "Project kickoff completed" {' in result
        assert "  author eve" in result
        assert "summary" not in result
        assert result.endswith("}")

    def test_entry_with_summary(self) -> None:
        """Generate a journal entry with an optional summary."""
        entry = JournalEntryRequest(
            entry_date=date(2024, 2, 5),
            author="alice",
            headline="Architecture decision: microservices",
            summary="Decided to use microservices architecture for the backend.",
        )
        result = self.generator.generate(entry)

        assert 'journalentry 2024-02-05 "Architecture decision: microservices" {' in result
        assert "  author alice" in result
        assert '  summary "Decided to use microservices architecture for the backend."' in result
        assert result.endswith("}")

    def test_entry_with_task_path(self) -> None:
        """Task path is stored in the model but not part of the journalentry syntax."""
        entry = JournalEntryRequest(
            task_path="acme.development.backend_api",
            entry_date=date(2024, 3, 15),
            author="bob",
            headline="Sprint review completed",
        )
        result = self.generator.generate(entry)

        # task_path is metadata for file placement, not in the journalentry block
        assert "acme.development.backend_api" not in result
        assert 'journalentry 2024-03-15 "Sprint review completed" {' in result
        assert "  author bob" in result

    def test_headline_with_quotes_escaped(self) -> None:
        """Double quotes in headline are escaped."""
        entry = JournalEntryRequest(
            entry_date=date(2024, 1, 10),
            author="eve",
            headline='Reviewed "API design" document',
        )
        result = self.generator.generate(entry)

        assert 'journalentry 2024-01-10 "Reviewed \\"API design\\" document" {' in result

    def test_summary_with_quotes_escaped(self) -> None:
        """Double quotes in summary are escaped."""
        entry = JournalEntryRequest(
            entry_date=date(2024, 1, 10),
            author="eve",
            headline="Design review",
            summary='The team said "looks good" and approved.',
        )
        result = self.generator.generate(entry)

        assert '  summary "The team said \\"looks good\\" and approved."' in result

    def test_date_format_is_iso(self) -> None:
        """Date is formatted as YYYY-MM-DD."""
        entry = JournalEntryRequest(
            entry_date=date(2025, 12, 31),
            author="alice",
            headline="Year-end review",
        )
        result = self.generator.generate(entry)

        assert "journalentry 2025-12-31" in result

    def test_output_structure(self) -> None:
        """Verify the overall structure of the generated output."""
        entry = JournalEntryRequest(
            entry_date=date(2024, 6, 15),
            author="bob",
            headline="Milestone reached",
            summary="All tasks completed on time.",
        )
        result = self.generator.generate(entry)
        lines = result.split("\n")

        assert len(lines) == 4
        assert lines[0] == 'journalentry 2024-06-15 "Milestone reached" {'
        assert lines[1] == "  author bob"
        assert lines[2] == '  summary "All tasks completed on time."'
        assert lines[3] == "}"

    def test_output_structure_without_summary(self) -> None:
        """Verify structure when summary is omitted."""
        entry = JournalEntryRequest(
            entry_date=date(2024, 6, 15),
            author="bob",
            headline="Milestone reached",
        )
        result = self.generator.generate(entry)
        lines = result.split("\n")

        assert len(lines) == 3
        assert lines[0] == 'journalentry 2024-06-15 "Milestone reached" {'
        assert lines[1] == "  author bob"
        assert lines[2] == "}"
