"""Unit tests for the reports page UI module."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from tj_chat.pages.reports import ReportsPageUI, _format_size


class TestReportsPageUI:
    """Tests for ReportsPageUI.list_reports() logic."""

    def test_list_reports_empty_directory(self, tmp_path: Path) -> None:
        """Returns empty list when reports directory has no HTML files."""
        page = ReportsPageUI(reports_dir=tmp_path)
        assert page.list_reports() == []

    def test_list_reports_nonexistent_directory(self, tmp_path: Path) -> None:
        """Returns empty list when reports directory does not exist."""
        missing_dir = tmp_path / "nonexistent"
        page = ReportsPageUI(reports_dir=missing_dir)
        assert page.list_reports() == []

    def test_list_reports_finds_html_files(self, tmp_path: Path) -> None:
        """Finds .html files in the reports directory."""
        (tmp_path / "overview.html").write_text("<html>report</html>")
        (tmp_path / "gantt.html").write_text("<html>gantt</html>")

        page = ReportsPageUI(reports_dir=tmp_path)
        reports = page.list_reports()

        assert len(reports) == 2
        names = {r.name for r in reports}
        assert "overview.html" in names
        assert "gantt.html" in names

    def test_list_reports_ignores_non_html_files(self, tmp_path: Path) -> None:
        """Ignores files that are not .html."""
        (tmp_path / "report.html").write_text("<html>report</html>")
        (tmp_path / "data.csv").write_text("a,b,c")
        (tmp_path / "notes.txt").write_text("notes")

        page = ReportsPageUI(reports_dir=tmp_path)
        reports = page.list_reports()

        assert len(reports) == 1
        assert reports[0].name == "report.html"

    def test_list_reports_path_uses_static_endpoint(self, tmp_path: Path) -> None:
        """Report paths point to the /report-files/ static endpoint."""
        (tmp_path / "status.html").write_text("<html>status</html>")

        page = ReportsPageUI(reports_dir=tmp_path)
        reports = page.list_reports()

        assert reports[0].path == "/report-files/status.html"

    def test_list_reports_includes_size(self, tmp_path: Path) -> None:
        """Report size reflects actual file size."""
        content = "<html>some content here</html>"
        (tmp_path / "test.html").write_text(content)

        page = ReportsPageUI(reports_dir=tmp_path)
        reports = page.list_reports()

        assert reports[0].size == len(content)

    def test_list_reports_sorted_newest_first(self, tmp_path: Path) -> None:
        """Reports are sorted by modification time, newest first."""
        old_file = tmp_path / "old.html"
        new_file = tmp_path / "new.html"

        old_file.write_text("<html>old</html>")
        # Set old file to an earlier mtime
        os.utime(old_file, (1000000, 1000000))

        new_file.write_text("<html>new</html>")
        # Set new file to a later mtime
        os.utime(new_file, (2000000, 2000000))

        page = ReportsPageUI(reports_dir=tmp_path)
        reports = page.list_reports()

        assert reports[0].name == "new.html"
        assert reports[1].name == "old.html"


class TestFormatSize:
    """Tests for the _format_size helper function."""

    def test_bytes(self) -> None:
        """Formats small sizes in bytes."""
        assert _format_size(500) == "500 B"

    def test_kilobytes(self) -> None:
        """Formats sizes in kilobytes."""
        assert _format_size(2048) == "2.0 KB"

    def test_megabytes(self) -> None:
        """Formats sizes in megabytes."""
        assert _format_size(1048576) == "1.0 MB"

    def test_zero_bytes(self) -> None:
        """Formats zero bytes."""
        assert _format_size(0) == "0 B"
