"""Property-based tests for navigation header completeness.

Feature: integrated-mail-and-reporting, Property 9: Navigation header completeness

**Validates: Requirements 5.1, 5.5**

Property 9: For any set of HTML report files in the report directory, the injected
navigation header in each report SHALL contain links to every other report in the set
and to the Report_Index.
"""

from __future__ import annotations

import re
from pathlib import Path

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from tj_utils.report_postprocess import ReportInfo, generate_nav_header

# --- Strategies ---

# Valid HTML filename stem: short alphanumeric with hyphens/underscores
_filename_alphabet = "abcdefghijklmnopqrstuvwxyz0123456789-_"
_valid_filename_stem = st.text(
    alphabet=_filename_alphabet,
    min_size=1,
    max_size=15,
)

# Report title: simple printable text
_valid_title = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyz ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
    min_size=1,
    max_size=30,
)


@st.composite
def report_set(draw: st.DrawFn) -> list[ReportInfo]:
    """Generate a set of ReportInfo objects with unique filenames.

    Ensures no duplicate filenames and at least 2 reports to make
    cross-linking meaningful.
    """
    count = draw(st.integers(min_value=2, max_value=8))
    reports: list[ReportInfo] = []
    seen_filenames: set[str] = set()

    attempts = 0
    while len(reports) < count and attempts < count * 3:
        attempts += 1
        stem = draw(_valid_filename_stem)
        filename = f"{stem}.html"
        # Ensure unique filenames and avoid collision with index.html
        if filename in seen_filenames or filename == "index.html":
            continue
        seen_filenames.add(filename)
        title = draw(_valid_title)
        reports.append(
            ReportInfo(filename=filename, title=title, filepath=Path(f"/tmp/reports/{filename}"))
        )

    return reports


class TestNavHeaderCompleteness:
    """Property 9: Navigation header completeness.

    Feature: integrated-mail-and-reporting, Property 9: Navigation header completeness

    **Validates: Requirements 5.1, 5.5**
    """

    @given(reports=report_set())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.large_base_example])
    def test_nav_header_contains_links_to_all_other_reports(
        self, reports: list[ReportInfo]
    ) -> None:
        """For each report, the nav header contains links to all other reports in the set."""
        for active_report in reports:
            nav_html = generate_nav_header(reports, active_filename=active_report.filename)

            # Check that every report in the set has a link in the nav header
            for report in reports:
                assert f'href="{report.filename}"' in nav_html, (
                    f"Nav header for active report '{active_report.filename}' "
                    f"is missing link to '{report.filename}'.\n"
                    f"Nav HTML: {nav_html}"
                )

    @given(reports=report_set())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.large_base_example])
    def test_nav_header_contains_link_to_index(
        self, reports: list[ReportInfo]
    ) -> None:
        """For each report, the nav header contains a link to the Report_Index (index.html)."""
        for active_report in reports:
            nav_html = generate_nav_header(reports, active_filename=active_report.filename)

            assert 'href="index.html"' in nav_html, (
                f"Nav header for active report '{active_report.filename}' "
                f"is missing link to index.html (Report_Index).\n"
                f"Nav HTML: {nav_html}"
            )


# Regex to extract all href values from anchor tags
_HREF_RE = re.compile(r'<a\b[^>]*\bhref="([^"]*)"[^>]*>', re.IGNORECASE)
# Regex to find anchor tags with class="nav-active" (handles any attribute order)
_NAV_ACTIVE_RE = re.compile(
    r'<a\b[^>]*\bclass="nav-active"[^>]*>', re.IGNORECASE
)
# Regex to find all anchor tags (with or without nav-active class)
_ANCHOR_RE = re.compile(r'<a\b([^>]*)>', re.IGNORECASE)


class TestNavLinksRelativeAndActiveStyling:
    """Property 10: Navigation links are relative with active styling.

    Feature: integrated-mail-and-reporting, Property 10: Navigation links are relative
    with active styling

    **Validates: Requirements 5.2, 5.3**
    """

    @given(reports=report_set())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.large_base_example])
    def test_all_href_values_are_relative(
        self, reports: list[ReportInfo]
    ) -> None:
        """All href values in the nav header have no leading `/` or protocol prefix."""
        for active_report in reports:
            nav_html = generate_nav_header(reports, active_filename=active_report.filename)

            hrefs = _HREF_RE.findall(nav_html)
            assert len(hrefs) > 0, (
                f"No href values found in nav header for '{active_report.filename}'"
            )

            for href in hrefs:
                assert not href.startswith("/"), (
                    f"href '{href}' starts with '/' (absolute path) in nav header "
                    f"for active report '{active_report.filename}'"
                )
                assert not href.startswith("http://"), (
                    f"href '{href}' starts with 'http://' (protocol prefix) in nav header "
                    f"for active report '{active_report.filename}'"
                )
                assert not href.startswith("https://"), (
                    f"href '{href}' starts with 'https://' (protocol prefix) in nav header "
                    f"for active report '{active_report.filename}'"
                )

    @given(reports=report_set())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.large_base_example])
    def test_exactly_one_link_has_nav_active_class(
        self, reports: list[ReportInfo]
    ) -> None:
        """Exactly one link has class `nav-active` matching the active filename."""
        for active_report in reports:
            nav_html = generate_nav_header(reports, active_filename=active_report.filename)

            # Find all anchors with nav-active class and extract their hrefs
            active_hrefs: list[str] = []
            for anchor in _NAV_ACTIVE_RE.finditer(nav_html):
                href_match = re.search(r'href="([^"]*)"', anchor.group(0))
                if href_match:
                    active_hrefs.append(href_match.group(1))

            assert len(active_hrefs) == 1, (
                f"Expected exactly 1 nav-active link for active report "
                f"'{active_report.filename}', found {len(active_hrefs)}.\n"
                f"Active hrefs: {active_hrefs}\n"
                f"Nav HTML: {nav_html}"
            )

            # The active link's href should match the active filename
            assert active_hrefs[0] == active_report.filename, (
                f"nav-active link href '{active_hrefs[0]}' does not match "
                f"active filename '{active_report.filename}'"
            )

    @given(reports=report_set())
    @settings(max_examples=100, suppress_health_check=[HealthCheck.large_base_example])
    def test_non_active_links_do_not_have_nav_active_class(
        self, reports: list[ReportInfo]
    ) -> None:
        """All links other than the active report do NOT have the `nav-active` class."""
        for active_report in reports:
            nav_html = generate_nav_header(reports, active_filename=active_report.filename)

            # Find all anchor tags and check their attributes
            for anchor_match in _ANCHOR_RE.finditer(nav_html):
                attrs = anchor_match.group(1)
                href_match = re.search(r'href="([^"]*)"', attrs)
                if href_match is None:
                    continue

                href = href_match.group(1)
                has_nav_active = "nav-active" in attrs

                if href != active_report.filename:
                    assert not has_nav_active, (
                        f"Link to '{href}' has 'nav-active' class but is not the "
                        f"active report '{active_report.filename}'.\n"
                        f"Nav HTML: {nav_html}"
                    )
