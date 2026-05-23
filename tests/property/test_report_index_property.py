"""Property-based tests for Report Index completeness.

Feature: integrated-mail-and-reporting, Property 11: Report index completeness

**Validates: Requirements 5.4**

Property 11: For any set of HTML report files, the generated Report_Index SHALL contain
an entry for each report with its title and a relative link to its filename.
"""

from __future__ import annotations

from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_utils.report_postprocess import ReportInfo, generate_index

# --- Strategies ---

# Valid HTML filenames: alphanumeric with optional hyphens/underscores, ending in .html
_filename_base = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-",
    min_size=1,
    max_size=30,
)

# Report titles: printable text without HTML special chars that could break parsing
_title_text = st.text(
    alphabet=st.characters(
        categories=("L", "N", "Zs"),
        exclude_characters="<>&\"'\x00",
    ),
    min_size=1,
    max_size=60,
)


def _make_report_info(base: str, title: str) -> ReportInfo:
    """Create a ReportInfo from a filename base and title."""
    filename = f"{base}.html"
    filepath = Path(f"/tmp/reports/{filename}")
    return ReportInfo(filename=filename, title=title, filepath=filepath)


# Strategy for a unique list of ReportInfo objects.
# Uses unique_by on the filename base to avoid rejection sampling.
unique_report_set = st.lists(
    st.tuples(_filename_base, _title_text),
    min_size=1,
    max_size=15,
    unique_by=lambda t: t[0],
).map(lambda pairs: [_make_report_info(base, title) for base, title in pairs])


class TestReportIndexCompleteness:
    """Property 11: Report index completeness.

    Feature: integrated-mail-and-reporting, Property 11: Report index completeness

    **Validates: Requirements 5.4**
    """

    @given(reports=unique_report_set)
    @settings(max_examples=100)
    def test_index_contains_link_for_each_report(
        self, reports: list[ReportInfo]
    ) -> None:
        """The generated index SHALL contain a relative link (href) for each report."""
        index_html = generate_index(reports)

        for report in reports:
            expected_href = f'href="{report.filename}"'
            assert expected_href in index_html, (
                f"Expected link {expected_href!r} not found in index HTML. "
                f"Report: {report.filename}"
            )

    @given(reports=unique_report_set)
    @settings(max_examples=100)
    def test_index_contains_title_for_each_report(
        self, reports: list[ReportInfo]
    ) -> None:
        """The generated index SHALL contain the title text for each report."""
        index_html = generate_index(reports)

        for report in reports:
            # The title is HTML-escaped in the output
            escaped_title = (
                report.title
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
            )
            assert escaped_title in index_html, (
                f"Expected title {escaped_title!r} not found in index HTML. "
                f"Report: {report.filename}, title: {report.title!r}"
            )

    @given(reports=unique_report_set)
    @settings(max_examples=100)
    def test_index_links_are_relative(
        self, reports: list[ReportInfo]
    ) -> None:
        """All report links in the index SHALL be relative (no leading / or protocol)."""
        index_html = generate_index(reports)

        for report in reports:
            # Verify the href does not start with / or a protocol
            assert f'href="/{report.filename}"' not in index_html, (
                f"Link for {report.filename} has absolute path (leading /)"
            )
            assert f'href="http://' not in index_html, (
                "Index contains http:// protocol prefix in links"
            )
            assert f'href="https://' not in index_html, (
                "Index contains https:// protocol prefix in links"
            )
