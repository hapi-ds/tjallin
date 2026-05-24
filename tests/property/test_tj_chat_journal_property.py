"""Property-based tests for journal entry generation.

**Validates: Requirements 5.1**

Property 8: Journal entry generation produces valid syntax.
- For any valid JournalEntryRequest with a date, author, and headline (at most
  120 characters), the generated output SHALL be a syntactically valid TaskJuggler
  journalentry statement containing the date in YYYY-MM-DD format, the author
  resource ID, and the headline text.
"""

from __future__ import annotations

import re
from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.generators import JournalEntryGenerator
from tj_chat.models import JournalEntryRequest

# Strategy for valid dates (reasonable range for project management)
_dates = st.dates(min_value=date(2000, 1, 1), max_value=date(2099, 12, 31))

# Strategy for resource IDs: valid TaskJuggler identifiers (start with letter,
# alphanumeric + underscores)
_resource_id = st.text(
    alphabet=st.characters(categories=("Ll",), include_characters="_"),
    min_size=1,
    max_size=20,
).filter(lambda s: s[0].isalpha())

# Strategy for headlines: printable text, at most 120 characters, non-empty
_headline = st.text(
    alphabet=st.characters(
        categories=("L", "N", "Z", "P"),
        exclude_characters="\x00\r\n",
    ),
    min_size=1,
    max_size=120,
).filter(lambda s: s.strip() != "")

# Strategy for optional summaries: either None or non-empty text
_summary = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(
            categories=("L", "N", "Z", "P"),
            exclude_characters="\x00\r\n",
        ),
        min_size=1,
        max_size=200,
    ).filter(lambda s: s.strip() != ""),
)

# Strategy for optional task paths
_task_path = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(categories=("Ll", "N"), include_characters="_."),
        min_size=1,
        max_size=40,
    ).filter(lambda s: s[0].isalpha()),
)

# YYYY-MM-DD pattern
_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


def _count_structural_braces(text: str) -> int:
    """Count net structural braces (outside quoted strings).

    Returns 0 if braces are balanced, positive if more opens, negative if more closes.
    """
    net = 0
    in_quotes = False
    prev_char = ""
    for ch in text:
        if ch == '"' and prev_char != "\\":
            in_quotes = not in_quotes
        elif not in_quotes:
            if ch == "{":
                net += 1
            elif ch == "}":
                net -= 1
        prev_char = ch
    return net


class TestJournalEntryGenerationProperty:
    """Property 8: Journal entry generation produces valid syntax.

    **Validates: Requirements 5.1**
    """

    @given(
        entry_date=_dates,
        author=_resource_id,
        headline=_headline,
        summary=_summary,
        task_path=_task_path,
    )
    @settings(max_examples=200)
    def test_output_starts_with_journalentry_keyword(
        self,
        entry_date: date,
        author: str,
        headline: str,
        summary: str | None,
        task_path: str | None,
    ) -> None:
        """Generated output starts with the 'journalentry' keyword."""
        request = JournalEntryRequest(
            task_path=task_path,
            entry_date=entry_date,
            author=author,
            headline=headline,
            summary=summary,
        )
        generator = JournalEntryGenerator()
        output = generator.generate(request)

        assert output.startswith("journalentry "), (
            f"Output does not start with 'journalentry': {output!r}"
        )

    @given(
        entry_date=_dates,
        author=_resource_id,
        headline=_headline,
        summary=_summary,
        task_path=_task_path,
    )
    @settings(max_examples=200)
    def test_output_contains_date_in_yyyy_mm_dd_format(
        self,
        entry_date: date,
        author: str,
        headline: str,
        summary: str | None,
        task_path: str | None,
    ) -> None:
        """Generated output contains the date in YYYY-MM-DD format."""
        request = JournalEntryRequest(
            task_path=task_path,
            entry_date=entry_date,
            author=author,
            headline=headline,
            summary=summary,
        )
        generator = JournalEntryGenerator()
        output = generator.generate(request)

        expected_date = entry_date.isoformat()
        assert expected_date in output, (
            f"Expected date {expected_date!r} not found in output: {output!r}"
        )

        # Verify the date appears right after 'journalentry '
        first_line = output.split("\n")[0]
        date_match = _DATE_PATTERN.search(first_line)
        assert date_match is not None, (
            f"No YYYY-MM-DD date found in first line: {first_line!r}"
        )
        assert date_match.group() == expected_date

    @given(
        entry_date=_dates,
        author=_resource_id,
        headline=_headline,
        summary=_summary,
        task_path=_task_path,
    )
    @settings(max_examples=200)
    def test_output_contains_author_resource_id(
        self,
        entry_date: date,
        author: str,
        headline: str,
        summary: str | None,
        task_path: str | None,
    ) -> None:
        """Generated output contains the author resource ID."""
        request = JournalEntryRequest(
            task_path=task_path,
            entry_date=entry_date,
            author=author,
            headline=headline,
            summary=summary,
        )
        generator = JournalEntryGenerator()
        output = generator.generate(request)

        assert f"author {author}" in output, (
            f"Expected 'author {author}' not found in output: {output!r}"
        )

    @given(
        entry_date=_dates,
        author=_resource_id,
        headline=_headline,
        summary=_summary,
        task_path=_task_path,
    )
    @settings(max_examples=200)
    def test_output_contains_headline_text(
        self,
        entry_date: date,
        author: str,
        headline: str,
        summary: str | None,
        task_path: str | None,
    ) -> None:
        """Generated output contains the headline text (escaped if needed)."""
        request = JournalEntryRequest(
            task_path=task_path,
            entry_date=entry_date,
            author=author,
            headline=headline,
            summary=summary,
        )
        generator = JournalEntryGenerator()
        output = generator.generate(request)

        # The headline should appear in the first line, quoted
        escaped_headline = headline.replace('"', '\\"')
        assert f'"{escaped_headline}"' in output, (
            f"Expected headline {headline!r} (escaped: {escaped_headline!r}) "
            f"not found quoted in output: {output!r}"
        )

    @given(
        entry_date=_dates,
        author=_resource_id,
        headline=_headline,
        summary=_summary,
        task_path=_task_path,
    )
    @settings(max_examples=200)
    def test_output_has_valid_block_structure(
        self,
        entry_date: date,
        author: str,
        headline: str,
        summary: str | None,
        task_path: str | None,
    ) -> None:
        """Generated output has valid block structure with matching braces."""
        request = JournalEntryRequest(
            task_path=task_path,
            entry_date=entry_date,
            author=author,
            headline=headline,
            summary=summary,
        )
        generator = JournalEntryGenerator()
        output = generator.generate(request)

        # First line must contain opening brace (the block opener)
        first_line = output.split("\n")[0]
        assert first_line.rstrip().endswith("{"), (
            f"First line does not end with opening brace: {first_line!r}"
        )

        # Last line must be the closing brace
        assert output.rstrip().endswith("}"), (
            f"Output does not end with closing brace: {output!r}"
        )

        # Count structural braces (outside quoted strings) to verify balance
        structural_braces = _count_structural_braces(output)
        assert structural_braces == 0, (
            f"Unbalanced structural braces (net={structural_braces}) "
            f"in output: {output!r}"
        )

    @given(
        entry_date=_dates,
        author=_resource_id,
        headline=_headline,
        task_path=_task_path,
    )
    @settings(max_examples=200)
    def test_output_includes_summary_when_provided(
        self,
        entry_date: date,
        author: str,
        headline: str,
        task_path: str | None,
    ) -> None:
        """When summary is provided, it appears in the output."""
        summary_text = "This is a test summary for the journal entry."
        request = JournalEntryRequest(
            task_path=task_path,
            entry_date=entry_date,
            author=author,
            headline=headline,
            summary=summary_text,
        )
        generator = JournalEntryGenerator()
        output = generator.generate(request)

        assert "summary" in output, (
            f"Expected 'summary' keyword not found in output: {output!r}"
        )
        assert summary_text in output, (
            f"Expected summary text not found in output: {output!r}"
        )

    @given(
        entry_date=_dates,
        author=_resource_id,
        headline=_headline,
        task_path=_task_path,
    )
    @settings(max_examples=200)
    def test_output_excludes_summary_when_none(
        self,
        entry_date: date,
        author: str,
        headline: str,
        task_path: str | None,
    ) -> None:
        """When summary is None, no summary line appears in the output."""
        request = JournalEntryRequest(
            task_path=task_path,
            entry_date=entry_date,
            author=author,
            headline=headline,
            summary=None,
        )
        generator = JournalEntryGenerator()
        output = generator.generate(request)

        # No line should contain 'summary' as a keyword
        lines = output.split("\n")
        summary_lines = [line for line in lines if line.strip().startswith("summary")]
        assert len(summary_lines) == 0, (
            f"Unexpected summary line in output when summary is None: {output!r}"
        )
