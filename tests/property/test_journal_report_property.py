"""Property-based tests for journal report rendering and sort order.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

Property 12: Journal entry rendering completeness
- For any journal entry with date, author, summary, and associated task name,
  the Journal_Report output SHALL contain all provided fields. For entries
  missing author or summary, the report SHALL still render with available fields.

Property 13: Journal entry sort order
- For any set of journal entries, the Journal_Report SHALL display them in
  reverse chronological order (newest first), with entries sharing the same
  date ordered alphabetically by task name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Data model for journal entries (mirrors TJ3 journal attributes)
# ---------------------------------------------------------------------------


@dataclass
class JournalEntry:
    """A single journal entry as produced by TJ3.

    Attributes:
        task_name: The task this entry is associated with.
        entry_date: Date of the journal entry.
        author: Author of the entry (may be None if missing).
        summary: Summary text (may be None if missing).
    """

    task_name: str
    entry_date: date
    author: str | None
    summary: str | None


# ---------------------------------------------------------------------------
# Mock HTML renderer (simulates TJ3 journal report output)
# ---------------------------------------------------------------------------


def render_journal_entry_html(entry: JournalEntry) -> str:
    """Render a single journal entry as HTML, simulating TJ3 output format.

    TJ3 renders journal entries with task name, date, and optional author/summary.
    Missing fields are omitted from the output.

    Args:
        entry: The journal entry to render.

    Returns:
        HTML string for the entry.
    """
    parts = [
        f'<div class="journal-entry">',
        f'  <span class="task-name">{_escape_html(entry.task_name)}</span>',
        f'  <span class="entry-date">{entry.entry_date.isoformat()}</span>',
    ]
    if entry.author is not None:
        parts.append(f'  <span class="author">{_escape_html(entry.author)}</span>')
    if entry.summary is not None:
        parts.append(f'  <span class="summary">{_escape_html(entry.summary)}</span>')
    parts.append("</div>")
    return "\n".join(parts)


def render_journal_report_html(entries: list[JournalEntry]) -> str:
    """Render a full journal report as HTML, simulating TJ3 output.

    Entries are sorted in reverse chronological order (newest first).
    Entries with the same date are sorted alphabetically by task name.

    Args:
        entries: List of journal entries to render.

    Returns:
        Complete HTML document string for the journal report.
    """
    # Sort: reverse chronological, then alphabetical by task name for same date
    sorted_entries = sorted(entries, key=lambda e: (-e.entry_date.toordinal(), e.task_name))

    entry_html = "\n".join(render_journal_entry_html(e) for e in sorted_entries)

    return (
        "<html>\n"
        "<head><title>Project Journal</title></head>\n"
        "<body>\n"
        '<div class="journal-report">\n'
        f"{entry_html}\n"
        "</div>\n"
        "</body>\n"
        "</html>"
    )


def _escape_html(text: str) -> str:
    """Escape HTML special characters in text."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for task names: non-empty printable strings without HTML special chars
_task_name_st = st.text(
    alphabet=st.characters(categories=("L", "N", "Zs"), include_characters="-_"),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "")

# Strategy for author names
_author_st = st.text(
    alphabet=st.characters(categories=("L", "N", "Zs"), include_characters="-_."),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() != "")

# Strategy for summary text
_summary_st = st.text(
    alphabet=st.characters(categories=("L", "N", "Zs", "P"), include_characters=" "),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip() != "")

# Strategy for dates within a reasonable range
_date_st = st.dates(min_value=date(2020, 1, 1), max_value=date(2030, 12, 31))


@st.composite
def journal_entry_with_all_fields(draw: st.DrawFn) -> JournalEntry:
    """Generate a journal entry with all fields present."""
    return JournalEntry(
        task_name=draw(_task_name_st),
        entry_date=draw(_date_st),
        author=draw(_author_st),
        summary=draw(_summary_st),
    )


@st.composite
def journal_entry_with_optional_fields(draw: st.DrawFn) -> JournalEntry:
    """Generate a journal entry where author and summary may be missing."""
    return JournalEntry(
        task_name=draw(_task_name_st),
        entry_date=draw(_date_st),
        author=draw(st.one_of(st.none(), _author_st)),
        summary=draw(st.one_of(st.none(), _summary_st)),
    )


# ---------------------------------------------------------------------------
# Property 12: Journal entry rendering completeness
# ---------------------------------------------------------------------------


class TestJournalEntryRenderingCompleteness:
    """Property 12: Journal entry rendering completeness.

    **Validates: Requirements 6.1, 6.2, 6.3**

    For any journal entry with date, author, summary, and associated task name,
    the rendered output SHALL contain all provided fields. For entries missing
    author or summary, the report SHALL still render with available fields.
    """

    @given(entry=journal_entry_with_all_fields())
    @settings(max_examples=100)
    def test_all_fields_present_in_output(self, entry: JournalEntry) -> None:
        """When all fields are provided, all appear in the rendered HTML."""
        html = render_journal_entry_html(entry)

        assert _escape_html(entry.task_name) in html, (
            f"Task name '{entry.task_name}' not found in rendered HTML"
        )
        assert entry.entry_date.isoformat() in html, (
            f"Date '{entry.entry_date.isoformat()}' not found in rendered HTML"
        )
        assert _escape_html(entry.author) in html, (
            f"Author '{entry.author}' not found in rendered HTML"
        )
        assert _escape_html(entry.summary) in html, (
            f"Summary '{entry.summary}' not found in rendered HTML"
        )

    @given(entry=journal_entry_with_optional_fields())
    @settings(max_examples=100)
    def test_partial_fields_render_available_data(self, entry: JournalEntry) -> None:
        """When author or summary is missing, entry still renders with available fields."""
        html = render_journal_entry_html(entry)

        # Task name and date are always required and must be present
        assert _escape_html(entry.task_name) in html, (
            f"Task name '{entry.task_name}' not found in rendered HTML"
        )
        assert entry.entry_date.isoformat() in html, (
            f"Date '{entry.entry_date.isoformat()}' not found in rendered HTML"
        )

        # Optional fields: present only when provided
        if entry.author is not None:
            assert _escape_html(entry.author) in html, (
                f"Author '{entry.author}' should be in HTML when provided"
            )
        else:
            assert "author" not in html.lower() or 'class="author"' not in html, (
                "Author field should not appear when author is None"
            )

        if entry.summary is not None:
            assert _escape_html(entry.summary) in html, (
                f"Summary '{entry.summary}' should be in HTML when provided"
            )
        else:
            assert "summary" not in html.lower() or 'class="summary"' not in html, (
                "Summary field should not appear when summary is None"
            )

    @given(entries=st.lists(journal_entry_with_optional_fields(), min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_full_report_contains_all_entry_fields(
        self, entries: list[JournalEntry]
    ) -> None:
        """In a full report, every entry's provided fields appear in the output."""
        html = render_journal_report_html(entries)

        for entry in entries:
            assert _escape_html(entry.task_name) in html, (
                f"Task name '{entry.task_name}' missing from full report"
            )
            assert entry.entry_date.isoformat() in html, (
                f"Date '{entry.entry_date.isoformat()}' missing from full report"
            )
            if entry.author is not None:
                assert _escape_html(entry.author) in html, (
                    f"Author '{entry.author}' missing from full report"
                )
            if entry.summary is not None:
                assert _escape_html(entry.summary) in html, (
                    f"Summary '{entry.summary}' missing from full report"
                )


# ---------------------------------------------------------------------------
# Property 13: Journal entry sort order
# ---------------------------------------------------------------------------


class TestJournalEntrySortOrder:
    """Property 13: Journal entry sort order.

    **Validates: Requirements 6.4**

    For any set of journal entries, the Journal_Report SHALL display them in
    reverse chronological order (newest first), with entries sharing the same
    date ordered alphabetically by task name.
    """

    @given(entries=st.lists(journal_entry_with_all_fields(), min_size=2, max_size=20))
    @settings(max_examples=100)
    def test_entries_sorted_reverse_chronological(
        self, entries: list[JournalEntry]
    ) -> None:
        """Entries in the rendered report appear in reverse chronological order."""
        html = render_journal_report_html(entries)

        # Extract dates in order of appearance from the HTML
        date_pattern = re.compile(r'<span class="entry-date">(\d{4}-\d{2}-\d{2})</span>')
        rendered_dates = [
            date.fromisoformat(m.group(1)) for m in date_pattern.finditer(html)
        ]

        # Verify reverse chronological order (each date >= next date)
        for i in range(len(rendered_dates) - 1):
            assert rendered_dates[i] >= rendered_dates[i + 1], (
                f"Dates not in reverse chronological order at position {i}: "
                f"{rendered_dates[i]} should be >= {rendered_dates[i + 1]}"
            )

    @given(
        base_date=_date_st,
        task_names=st.lists(
            _task_name_st,
            min_size=2,
            max_size=10,
            unique=True,
        ),
    )
    @settings(max_examples=100)
    def test_same_date_entries_sorted_alphabetically_by_task(
        self, base_date: date, task_names: list[str]
    ) -> None:
        """Entries with the same date are sorted alphabetically by task name."""
        # Create entries all with the same date but different task names
        entries = [
            JournalEntry(
                task_name=name,
                entry_date=base_date,
                author="Author",
                summary="Summary",
            )
            for name in task_names
        ]

        html = render_journal_report_html(entries)

        # Extract task names in order of appearance
        task_pattern = re.compile(r'<span class="task-name">(.*?)</span>')
        rendered_tasks = [m.group(1) for m in task_pattern.finditer(html)]

        # All task names should be present
        assert len(rendered_tasks) == len(task_names), (
            f"Expected {len(task_names)} tasks, found {len(rendered_tasks)}"
        )

        # When dates are the same, tasks should be in alphabetical order
        expected_order = sorted(_escape_html(name) for name in task_names)
        assert rendered_tasks == expected_order, (
            f"Tasks with same date not in alphabetical order.\n"
            f"Expected: {expected_order}\n"
            f"Got: {rendered_tasks}"
        )

    @given(entries=st.lists(journal_entry_with_all_fields(), min_size=1, max_size=20))
    @settings(max_examples=100)
    def test_entry_count_preserved(self, entries: list[JournalEntry]) -> None:
        """The rendered report contains exactly as many entries as provided."""
        html = render_journal_report_html(entries)

        entry_pattern = re.compile(r'<div class="journal-entry">')
        rendered_count = len(entry_pattern.findall(html))

        assert rendered_count == len(entries), (
            f"Expected {len(entries)} entries in report, found {rendered_count}"
        )
