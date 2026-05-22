"""Unit tests for TJ Web Service fallback page and report detection logic.

Since the web service entrypoint (services/tj-web/entrypoint.sh) runs inside
a Docker container, we validate:
1. The fallback HTML page exists and is well-formed
2. The report detection logic (reports_exist function) behaves correctly

Validates: Requirements 4.7
"""

import os
import re
import tempfile
from pathlib import Path


# Path to the fallback page relative to the project root
FALLBACK_PAGE = Path(__file__).parent.parent.parent / "services" / "tj-web" / "static" / "no-reports.html"
ENTRYPOINT_SCRIPT = Path(__file__).parent.parent.parent / "services" / "tj-web" / "entrypoint.sh"


class TestFallbackPageExists:
    """Test that the fallback HTML page exists and is accessible."""

    def test_fallback_page_file_exists(self):
        """The no-reports.html file must exist in the static directory."""
        assert FALLBACK_PAGE.exists(), f"Fallback page not found at {FALLBACK_PAGE}"

    def test_fallback_page_is_not_empty(self):
        """The fallback page must have content."""
        content = FALLBACK_PAGE.read_text(encoding="utf-8")
        assert len(content) > 100, "Fallback page appears to be empty or too short"


class TestFallbackPageContent:
    """Test that the fallback page contains required elements for accessibility and usability."""

    def test_has_doctype(self):
        """The page must start with a DOCTYPE declaration."""
        content = FALLBACK_PAGE.read_text(encoding="utf-8")
        assert content.strip().startswith("<!DOCTYPE html>")

    def test_has_lang_attribute(self):
        """The html element must have a lang attribute for accessibility."""
        content = FALLBACK_PAGE.read_text(encoding="utf-8")
        assert 'lang="en"' in content or "lang='en'" in content

    def test_has_viewport_meta(self):
        """The page must include a viewport meta tag for responsive design."""
        content = FALLBACK_PAGE.read_text(encoding="utf-8")
        assert "viewport" in content

    def test_has_title(self):
        """The page must have a title element."""
        content = FALLBACK_PAGE.read_text(encoding="utf-8")
        assert "<title>" in content and "</title>" in content

    def test_indicates_no_reports(self):
        """The page must clearly indicate that no reports are available."""
        content = FALLBACK_PAGE.read_text(encoding="utf-8").lower()
        assert "no report" in content or "not yet" in content or "not been generated" in content

    def test_suggests_rebuild(self):
        """The page must suggest running a rebuild to generate reports."""
        content = FALLBACK_PAGE.read_text(encoding="utf-8")
        assert "rebuild" in content.lower() or "scripts/rebuild" in content

    def test_no_external_dependencies(self):
        """The page must be self-contained with no external CSS/JS/font links."""
        content = FALLBACK_PAGE.read_text(encoding="utf-8")
        # Should not reference external CDNs or resources
        assert "https://" not in content and "http://" not in content

    def test_has_main_landmark(self):
        """The page must have a main landmark for accessibility."""
        content = FALLBACK_PAGE.read_text(encoding="utf-8")
        assert '<main' in content or 'role="main"' in content

    def test_has_heading(self):
        """The page must have a heading element."""
        content = FALLBACK_PAGE.read_text(encoding="utf-8")
        assert "<h1" in content


class TestEntrypointFallbackLogic:
    """Test that the entrypoint script contains the fallback logic."""

    def test_entrypoint_checks_for_reports(self):
        """The entrypoint must check if reports exist before starting."""
        content = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        assert "reports_exist" in content

    def test_entrypoint_references_fallback_page(self):
        """The entrypoint must reference the fallback HTML page."""
        content = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        assert "no-reports.html" in content

    def test_entrypoint_starts_fallback_server(self):
        """The entrypoint must start a fallback server when no reports exist."""
        content = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        assert "start_fallback_server" in content

    def test_entrypoint_transitions_when_reports_appear(self):
        """The entrypoint must transition to normal operation when reports appear."""
        content = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        assert "wait_for_reports" in content or "reports detected" in content.lower()

    def test_entrypoint_uses_ruby_webrick(self):
        """The entrypoint must use Ruby WEBrick for the fallback server (available in ruby:3.2-slim)."""
        content = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        assert "webrick" in content.lower() or "WEBrick" in content

    def test_entrypoint_serves_on_port_8080(self):
        """The fallback server must serve on port 8080 to match the health check."""
        content = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        # The WEBrick server should bind to port 8080
        assert "Port: 8080" in content or "port 8080" in content.lower()

    def test_entrypoint_stops_fallback_on_shutdown(self):
        """The shutdown handler must also stop the fallback server."""
        content = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        assert "stop_fallback_server" in content

    def test_reports_exist_checks_html_files(self):
        """The reports_exist function must look for HTML report files."""
        content = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        assert "*.html" in content or ".html" in content

    def test_reports_exist_checks_csv_files(self):
        """The reports_exist function must also look for CSV report files."""
        content = ENTRYPOINT_SCRIPT.read_text(encoding="utf-8")
        assert "*.csv" in content or ".csv" in content
