"""Unit tests for journal report definition in project/includes/reports.tji.

Validates that the JournalReport TJ3 definition is syntactically valid and
contains all required elements for rendering journal entries.

Requirements: 6.1, 6.6
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPORTS_FILE = Path(__file__).resolve().parents[2] / "project" / "includes" / "reports.tji"


@pytest.fixture
def report_content() -> str:
    """Read the reports.tji file content."""
    assert REPORTS_FILE.exists(), f"Report file not found: {REPORTS_FILE}"
    return REPORTS_FILE.read_text(encoding="utf-8")


@pytest.fixture
def journal_block(report_content: str) -> str:
    """Extract the JournalReport block from the reports file."""
    # Find the taskreport JournalReport block by matching balanced braces
    pattern = r"(taskreport\s+JournalReport\b[^{]*\{)"
    match = re.search(pattern, report_content)
    assert match is not None, "JournalReport declaration not found in reports.tji"

    start = match.start()
    # Walk forward to find the matching closing brace
    brace_count = 0
    pos = match.end() - 1  # position of the opening brace
    for i in range(pos, len(report_content)):
        if report_content[i] == "{":
            brace_count += 1
        elif report_content[i] == "}":
            brace_count -= 1
            if brace_count == 0:
                return report_content[start : i + 1]

    pytest.fail("Could not find matching closing brace for JournalReport block")


class TestJournalReportDeclaration:
    """Tests that the JournalReport definition exists and is properly declared."""

    def test_taskreport_declaration_exists(self, report_content: str) -> None:
        """Should declare a taskreport named JournalReport."""
        assert re.search(
            r"taskreport\s+JournalReport\b", report_content
        ), "Missing 'taskreport JournalReport' declaration"

    def test_journalmode_journal(self, journal_block: str) -> None:
        """Should set journalmode to journal for displaying journal entries."""
        assert re.search(
            r"\bjournalmode\s+journal\b", journal_block
        ), "Missing 'journalmode journal' directive"

    def test_columns_name_and_journal(self, journal_block: str) -> None:
        """Should include name and journal columns."""
        assert re.search(
            r"\bcolumns\s+name\s*,\s*journal\b", journal_block
        ), "Missing 'columns name, journal' directive"

    def test_journalattributes(self, journal_block: str) -> None:
        """Should configure journalattributes with headline, author, date, summary."""
        assert re.search(
            r"\bjournalattributes\s+headline\s*,\s*author\s*,\s*date\s*,\s*summary\b",
            journal_block,
        ), "Missing 'journalattributes headline, author, date, summary' directive"

    def test_formats_html(self, journal_block: str) -> None:
        """Should output in HTML format."""
        assert re.search(
            r"\bformats\s+html\b", journal_block
        ), "Missing 'formats html' directive"


class TestJournalReportSyntax:
    """Tests that the JournalReport block is syntactically valid TJ3."""

    def test_balanced_braces(self, journal_block: str) -> None:
        """Should have balanced opening and closing braces."""
        open_count = journal_block.count("{")
        close_count = journal_block.count("}")
        assert open_count == close_count, (
            f"Unbalanced braces: {open_count} opening vs {close_count} closing"
        )

    def test_no_unknown_top_level_keywords(self, journal_block: str) -> None:
        """Should only contain recognized TJ3 taskreport keywords."""
        # Extract lines that are directives (not comments, not braces-only)
        valid_keywords = {
            "taskreport",
            "formats",
            "headline",
            "columns",
            "journalmode",
            "journalattributes",
            "sortjournals",
            "hidetask",
            "hideresource",
            "sorttasks",
            "timeformat",
            "loadunit",
            "caption",
            "period",
            "start",
            "end",
        }
        lines = journal_block.splitlines()
        for line in lines:
            stripped = line.strip()
            # Skip empty lines, comments, and brace-only lines
            if not stripped or stripped.startswith("/*") or stripped.startswith("*"):
                continue
            if stripped in ("{", "}"):
                continue
            # Extract the first word as the keyword
            first_word_match = re.match(r"(\w+)", stripped)
            if first_word_match:
                keyword = first_word_match.group(1)
                assert keyword in valid_keywords, (
                    f"Unrecognized keyword '{keyword}' in JournalReport block"
                )

    def test_block_starts_with_taskreport(self, journal_block: str) -> None:
        """Should start with the taskreport keyword."""
        assert journal_block.strip().startswith("taskreport")


class TestEmptyJournalEntriesHandling:
    """Tests for the empty journal entries scenario (Requirement 6.6).

    TJ3 v3.8.4 does not support `hasjournal()` function. When no journal
    entries exist, the journal column simply renders empty. The journalmode
    directive ensures journal entries are displayed when present.
    """

    def test_journalmode_handles_empty_case(self, journal_block: str) -> None:
        """Should use journalmode journal to display entries when present.

        When no journal entries exist, the journal column renders empty
        which effectively indicates no entries are available.
        """
        assert "journalmode" in journal_block
        assert re.search(
            r"\bjournalmode\s+journal\b", journal_block
        ), "Should use 'journalmode journal' for rendering journal entries"
