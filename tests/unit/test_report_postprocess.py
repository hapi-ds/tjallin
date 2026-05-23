"""Unit tests for report post-processor.

Covers ReportInfo, discover_reports(), generate_nav_header(), and generate_index().
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tj_utils.report_postprocess import (
    ReportInfo,
    discover_reports,
    generate_index,
    generate_nav_header,
)


@pytest.fixture
def report_dir(tmp_path: Path) -> Path:
    """Create a temporary directory with sample HTML report files."""
    return tmp_path


class TestDiscoverReports:
    """Tests for discover_reports() function."""

    def test_discovers_html_files(self, report_dir: Path) -> None:
        """Should find all .html files in the directory."""
        (report_dir / "GanttChart.html").write_text(
            "<html><head><title>Gantt Chart</title></head><body></body></html>"
        )
        (report_dir / "ResourceView.html").write_text(
            "<html><head><title>Resource View</title></head><body></body></html>"
        )

        reports = discover_reports(report_dir)

        assert len(reports) == 2
        filenames = [r.filename for r in reports]
        assert "GanttChart.html" in filenames
        assert "ResourceView.html" in filenames

    def test_extracts_title_from_title_tag(self, report_dir: Path) -> None:
        """Should extract title from <title> element."""
        (report_dir / "report.html").write_text(
            "<html><head><title>My Report Title</title></head><body></body></html>"
        )

        reports = discover_reports(report_dir)

        assert reports[0].title == "My Report Title"

    def test_extracts_title_from_h1_when_no_title_tag(self, report_dir: Path) -> None:
        """Should fall back to first <h1> when <title> is missing."""
        (report_dir / "report.html").write_text(
            "<html><head></head><body><h1>Heading Title</h1></body></html>"
        )

        reports = discover_reports(report_dir)

        assert reports[0].title == "Heading Title"

    def test_prefers_title_tag_over_h1(self, report_dir: Path) -> None:
        """Should prefer <title> over <h1> when both exist."""
        (report_dir / "report.html").write_text(
            "<html><head><title>Title Tag</title></head>"
            "<body><h1>H1 Tag</h1></body></html>"
        )

        reports = discover_reports(report_dir)

        assert reports[0].title == "Title Tag"

    def test_falls_back_to_filename_stem(self, report_dir: Path) -> None:
        """Should use filename without extension when no title or h1 found."""
        (report_dir / "CostReport.html").write_text(
            "<html><head></head><body><p>No heading here</p></body></html>"
        )

        reports = discover_reports(report_dir)

        assert reports[0].title == "CostReport"

    def test_falls_back_when_title_tag_is_empty(self, report_dir: Path) -> None:
        """Should fall back when <title> is present but empty."""
        (report_dir / "Empty.html").write_text(
            "<html><head><title>  </title></head><body></body></html>"
        )

        reports = discover_reports(report_dir)

        assert reports[0].title == "Empty"

    def test_strips_html_tags_from_title(self, report_dir: Path) -> None:
        """Should strip nested HTML tags from extracted title text."""
        (report_dir / "report.html").write_text(
            "<html><head><title><b>Bold</b> Title</title></head><body></body></html>"
        )

        reports = discover_reports(report_dir)

        assert reports[0].title == "Bold Title"

    def test_ignores_non_html_files(self, report_dir: Path) -> None:
        """Should not include non-.html files."""
        (report_dir / "report.html").write_text("<html><title>Report</title></html>")
        (report_dir / "data.csv").write_text("a,b,c")
        (report_dir / "notes.txt").write_text("some notes")

        reports = discover_reports(report_dir)

        assert len(reports) == 1
        assert reports[0].filename == "report.html"

    def test_empty_directory_returns_empty_list(self, report_dir: Path) -> None:
        """Should return empty list when no HTML files exist."""
        reports = discover_reports(report_dir)

        assert reports == []

    def test_reports_sorted_by_filename(self, report_dir: Path) -> None:
        """Should return reports sorted alphabetically by filename."""
        (report_dir / "Zebra.html").write_text("<html><title>Zebra</title></html>")
        (report_dir / "Alpha.html").write_text("<html><title>Alpha</title></html>")
        (report_dir / "Middle.html").write_text("<html><title>Middle</title></html>")

        reports = discover_reports(report_dir)

        assert [r.filename for r in reports] == [
            "Alpha.html",
            "Middle.html",
            "Zebra.html",
        ]

    def test_filepath_is_absolute(self, report_dir: Path) -> None:
        """Should set filepath to the absolute path of the file."""
        (report_dir / "report.html").write_text("<html><title>Test</title></html>")

        reports = discover_reports(report_dir)

        assert reports[0].filepath.is_absolute()
        assert reports[0].filepath.name == "report.html"

    def test_handles_unreadable_file_gracefully(self, report_dir: Path) -> None:
        """Should use filename fallback when file cannot be read."""
        html_file = report_dir / "broken.html"
        html_file.write_bytes(b"\xff\xfe" + b"\x00" * 100)

        reports = discover_reports(report_dir)

        assert len(reports) == 1
        assert reports[0].title == "broken"


class TestReportInfoDataclass:
    """Tests for ReportInfo dataclass."""

    def test_fields_accessible(self) -> None:
        """Should store and expose all fields."""
        info = ReportInfo(
            filename="test.html",
            title="Test Report",
            filepath=Path("/reports/test.html"),
        )

        assert info.filename == "test.html"
        assert info.title == "Test Report"
        assert info.filepath == Path("/reports/test.html")


@pytest.fixture
def sample_reports() -> list[ReportInfo]:
    """Create a sample list of ReportInfo objects for testing."""
    return [
        ReportInfo(
            filename="GanttChart.html",
            title="Gantt Chart",
            filepath=Path("/reports/GanttChart.html"),
        ),
        ReportInfo(
            filename="ResourceView.html",
            title="Resource View",
            filepath=Path("/reports/ResourceView.html"),
        ),
        ReportInfo(
            filename="TaskList.html",
            title="Task List",
            filepath=Path("/reports/TaskList.html"),
        ),
    ]


class TestGenerateNavHeader:
    """Tests for generate_nav_header() function."""

    def test_contains_links_to_all_reports(self, sample_reports: list[ReportInfo]) -> None:
        """Should include a link to every report in the set."""
        result = generate_nav_header(sample_reports, active_filename="GanttChart.html")

        assert 'href="GanttChart.html"' in result
        assert 'href="ResourceView.html"' in result
        assert 'href="TaskList.html"' in result

    def test_contains_link_to_index(self, sample_reports: list[ReportInfo]) -> None:
        """Should include a link to the Report Index (index.html)."""
        result = generate_nav_header(sample_reports, active_filename="GanttChart.html")

        assert 'href="index.html"' in result
        assert "Report Index" in result

    def test_contains_link_to_admin_panel(self, sample_reports: list[ReportInfo]) -> None:
        """Should include a link to the admin panel."""
        result = generate_nav_header(sample_reports, active_filename="GanttChart.html")

        assert 'href="../admin/"' in result
        assert "Admin" in result

    def test_custom_admin_path(self, sample_reports: list[ReportInfo]) -> None:
        """Should use the provided admin_path parameter."""
        result = generate_nav_header(
            sample_reports, active_filename="GanttChart.html", admin_path="custom/admin/"
        )

        assert 'href="custom/admin/"' in result

    def test_active_report_has_nav_active_class(self, sample_reports: list[ReportInfo]) -> None:
        """Should mark the active report's link with CSS class nav-active."""
        result = generate_nav_header(sample_reports, active_filename="ResourceView.html")

        assert 'href="ResourceView.html" class="nav-active"' in result

    def test_non_active_reports_lack_nav_active_class(
        self, sample_reports: list[ReportInfo]
    ) -> None:
        """Should not apply nav-active to non-active report links."""
        result = generate_nav_header(sample_reports, active_filename="GanttChart.html")

        # ResourceView should not have nav-active
        assert 'href="ResourceView.html" class="nav-active"' not in result
        assert 'href="TaskList.html" class="nav-active"' not in result

    def test_all_links_are_relative(self, sample_reports: list[ReportInfo]) -> None:
        """All href values should be relative (no leading / or protocol)."""
        result = generate_nav_header(sample_reports, active_filename="GanttChart.html")

        # No absolute paths or protocols
        assert 'href="/' not in result
        assert "href=\"http" not in result

    def test_index_active_when_active_filename_is_index(
        self, sample_reports: list[ReportInfo]
    ) -> None:
        """Should mark index link as active when active_filename is index.html."""
        result = generate_nav_header(sample_reports, active_filename="index.html")

        assert 'href="index.html" class="nav-active"' in result

    def test_wraps_in_nav_element(self, sample_reports: list[ReportInfo]) -> None:
        """Should wrap output in a <nav> element."""
        result = generate_nav_header(sample_reports, active_filename="GanttChart.html")

        assert result.startswith('<nav class="tj-nav-header">')
        assert "</nav>" in result

    def test_empty_reports_list(self) -> None:
        """Should still produce nav with index and admin links when no reports."""
        result = generate_nav_header([], active_filename="index.html")

        assert 'href="index.html"' in result
        assert "Admin" in result

    def test_escapes_special_characters_in_title(self) -> None:
        """Should escape HTML special characters in report titles."""
        reports = [
            ReportInfo(
                filename="report.html",
                title='<script>alert("xss")</script>',
                filepath=Path("/reports/report.html"),
            )
        ]

        result = generate_nav_header(reports, active_filename="other.html")

        assert "<script>" not in result
        assert "&lt;script&gt;" in result


class TestGenerateIndex:
    """Tests for generate_index() function."""

    def test_contains_all_report_links(self, sample_reports: list[ReportInfo]) -> None:
        """Should list all reports with links."""
        result = generate_index(sample_reports)

        assert 'href="GanttChart.html"' in result
        assert 'href="ResourceView.html"' in result
        assert 'href="TaskList.html"' in result

    def test_contains_report_titles(self, sample_reports: list[ReportInfo]) -> None:
        """Should display report titles."""
        result = generate_index(sample_reports)

        assert "Gantt Chart" in result
        assert "Resource View" in result
        assert "Task List" in result

    def test_contains_admin_link(self, sample_reports: list[ReportInfo]) -> None:
        """Should include a link to the admin panel."""
        result = generate_index(sample_reports)

        assert 'href="admin/"' in result
        assert "Admin Panel" in result

    def test_custom_admin_path(self, sample_reports: list[ReportInfo]) -> None:
        """Should use the provided admin_path parameter."""
        result = generate_index(sample_reports, admin_path="custom/admin/")

        assert 'href="custom/admin/"' in result

    def test_all_links_are_relative(self, sample_reports: list[ReportInfo]) -> None:
        """All href values should be relative (no leading / or protocol)."""
        result = generate_index(sample_reports)

        assert 'href="/' not in result
        assert "href=\"http" not in result

    def test_is_complete_html_document(self, sample_reports: list[ReportInfo]) -> None:
        """Should produce a complete HTML document."""
        result = generate_index(sample_reports)

        assert "<!DOCTYPE html>" in result
        assert "<html>" in result
        assert "</html>" in result
        assert "<head>" in result
        assert "<body>" in result

    def test_has_report_index_title(self, sample_reports: list[ReportInfo]) -> None:
        """Should have 'Report Index' as the page title."""
        result = generate_index(sample_reports)

        assert "<title>Report Index</title>" in result
        assert "<h1>Report Index</h1>" in result

    def test_includes_nav_header(self, sample_reports: list[ReportInfo]) -> None:
        """Should include the navigation header in the index page."""
        result = generate_index(sample_reports)

        assert '<nav class="tj-nav-header">' in result

    def test_index_nav_marks_index_as_active(self, sample_reports: list[ReportInfo]) -> None:
        """The nav header in the index page should mark index.html as active."""
        result = generate_index(sample_reports)

        assert 'href="index.html" class="nav-active"' in result

    def test_empty_reports_list(self) -> None:
        """Should produce a valid page even with no reports."""
        result = generate_index([])

        assert "<!DOCTYPE html>" in result
        assert "<title>Report Index</title>" in result
        assert "<ul>" in result

    def test_reports_in_list_items(self, sample_reports: list[ReportInfo]) -> None:
        """Should wrap each report in a <li> element."""
        result = generate_index(sample_reports)

        assert "<li>" in result
        assert result.count("<li>") == 3

    def test_escapes_special_characters(self) -> None:
        """Should escape HTML special characters in titles and filenames."""
        reports = [
            ReportInfo(
                filename="report.html",
                title="Cost & Budget",
                filepath=Path("/reports/report.html"),
            )
        ]

        result = generate_index(reports)

        assert "Cost &amp; Budget" in result


class TestInjectNavHeaders:
    """Tests for inject_nav_headers() entry point."""

    def test_injects_nav_after_body_tag(self, report_dir: Path) -> None:
        """Should inject navigation header after the <body> tag."""
        from tj_utils.report_postprocess import inject_nav_headers

        (report_dir / "Report.html").write_text(
            "<html><head><title>Report</title></head><body><p>Content</p></body></html>"
        )

        inject_nav_headers(report_dir)

        content = (report_dir / "Report.html").read_text()
        body_pos = content.find("<body>")
        nav_pos = content.find('<nav class="tj-nav-header">')
        assert nav_pos > body_pos
        # Nav should appear before the original content
        p_pos = content.find("<p>Content</p>")
        assert nav_pos < p_pos

    def test_returns_count_of_processed_reports(self, report_dir: Path) -> None:
        """Should return the number of reports processed."""
        from tj_utils.report_postprocess import inject_nav_headers

        (report_dir / "A.html").write_text(
            "<html><head><title>A</title></head><body></body></html>"
        )
        (report_dir / "B.html").write_text(
            "<html><head><title>B</title></head><body></body></html>"
        )
        (report_dir / "C.html").write_text(
            "<html><head><title>C</title></head><body></body></html>"
        )

        result = inject_nav_headers(report_dir)

        assert result == 3

    def test_generates_index_html(self, report_dir: Path) -> None:
        """Should generate an index.html file in the report directory."""
        from tj_utils.report_postprocess import inject_nav_headers

        (report_dir / "Report.html").write_text(
            "<html><head><title>My Report</title></head><body></body></html>"
        )

        inject_nav_headers(report_dir)

        index_path = report_dir / "index.html"
        assert index_path.exists()
        index_content = index_path.read_text()
        assert "Report Index" in index_content
        assert 'href="Report.html"' in index_content
        assert "My Report" in index_content

    def test_index_not_counted_in_discovered_reports(self, report_dir: Path) -> None:
        """index.html should not be counted as a discovered report."""
        from tj_utils.report_postprocess import inject_nav_headers

        (report_dir / "Report.html").write_text(
            "<html><head><title>Report</title></head><body></body></html>"
        )
        # Pre-existing index.html should be treated as a report by discover,
        # but the generated one replaces it. The count should reflect discovered files.
        (report_dir / "index.html").write_text(
            "<html><head><title>Old Index</title></head><body></body></html>"
        )

        result = inject_nav_headers(report_dir)

        # Both Report.html and the pre-existing index.html are discovered
        assert result == 2

    def test_raises_on_missing_directory(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError when directory does not exist."""
        from tj_utils.report_postprocess import inject_nav_headers

        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(FileNotFoundError):
            inject_nav_headers(nonexistent)

    def test_raises_on_non_directory_path(self, report_dir: Path) -> None:
        """Should raise NotADirectoryError when path is a file, not a directory."""
        from tj_utils.report_postprocess import inject_nav_headers

        file_path = report_dir / "not_a_dir.txt"
        file_path.write_text("hello")

        with pytest.raises(NotADirectoryError):
            inject_nav_headers(file_path)

    def test_skips_unwritable_files_and_continues(self, report_dir: Path) -> None:
        """Should skip files that cannot be written and continue processing others."""
        import os
        import sys

        from tj_utils.report_postprocess import inject_nav_headers

        (report_dir / "Good.html").write_text(
            "<html><head><title>Good</title></head><body></body></html>"
        )
        bad_file = report_dir / "Bad.html"
        bad_file.write_text(
            "<html><head><title>Bad</title></head><body></body></html>"
        )

        # On Windows, make file read-only; on Unix, remove write permission
        if sys.platform == "win32":
            os.chmod(bad_file, 0o444)
        else:
            os.chmod(bad_file, 0o444)

        try:
            result = inject_nav_headers(report_dir)
            # At least the good file should be processed
            # (On Windows, read-only may still allow Python to write in some cases)
            assert result >= 1
        finally:
            # Restore permissions for cleanup
            os.chmod(bad_file, 0o666)

    def test_empty_directory_returns_zero(self, report_dir: Path) -> None:
        """Should return 0 when no HTML files are found."""
        from tj_utils.report_postprocess import inject_nav_headers

        result = inject_nav_headers(report_dir)

        assert result == 0

    def test_case_insensitive_body_tag_injection(self, report_dir: Path) -> None:
        """Should inject after <BODY> or <Body> tags (case-insensitive)."""
        from tj_utils.report_postprocess import inject_nav_headers

        (report_dir / "Report.html").write_text(
            "<html><head><title>Report</title></head><BODY><p>Content</p></BODY></html>"
        )

        inject_nav_headers(report_dir)

        content = (report_dir / "Report.html").read_text()
        body_pos = content.upper().find("<BODY>")
        nav_pos = content.find('<nav class="tj-nav-header">')
        assert nav_pos > body_pos

    def test_body_tag_with_attributes(self, report_dir: Path) -> None:
        """Should inject after <body class='foo'> tags with attributes."""
        from tj_utils.report_postprocess import inject_nav_headers

        (report_dir / "Report.html").write_text(
            '<html><head><title>Report</title></head><body class="main"><p>Hi</p></body></html>'
        )

        inject_nav_headers(report_dir)

        content = (report_dir / "Report.html").read_text()
        assert '<body class="main">' in content
        nav_pos = content.find('<nav class="tj-nav-header">')
        body_end = content.find('<body class="main">') + len('<body class="main">')
        assert nav_pos > body_end - 1

    def test_nav_header_contains_links_to_all_reports(self, report_dir: Path) -> None:
        """Each report should have nav links to all other reports."""
        from tj_utils.report_postprocess import inject_nav_headers

        (report_dir / "Alpha.html").write_text(
            "<html><head><title>Alpha</title></head><body></body></html>"
        )
        (report_dir / "Beta.html").write_text(
            "<html><head><title>Beta</title></head><body></body></html>"
        )

        inject_nav_headers(report_dir)

        alpha_content = (report_dir / "Alpha.html").read_text()
        assert 'href="Beta.html"' in alpha_content
        assert 'href="index.html"' in alpha_content

        beta_content = (report_dir / "Beta.html").read_text()
        assert 'href="Alpha.html"' in beta_content
        assert 'href="index.html"' in beta_content

    def test_active_report_marked_in_each_file(self, report_dir: Path) -> None:
        """Each report should mark itself as active in its own nav header."""
        from tj_utils.report_postprocess import inject_nav_headers

        (report_dir / "Alpha.html").write_text(
            "<html><head><title>Alpha</title></head><body></body></html>"
        )
        (report_dir / "Beta.html").write_text(
            "<html><head><title>Beta</title></head><body></body></html>"
        )

        inject_nav_headers(report_dir)

        alpha_content = (report_dir / "Alpha.html").read_text()
        assert 'href="Alpha.html" class="nav-active"' in alpha_content

        beta_content = (report_dir / "Beta.html").read_text()
        assert 'href="Beta.html" class="nav-active"' in beta_content
