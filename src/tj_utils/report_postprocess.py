"""Report post-processing for TaskJuggler HTML reports.

Discovers HTML report files and extracts metadata for cross-linked
navigation, generates navigation headers with relative links, and
produces a Report_Index page listing all reports.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ReportInfo:
    """Metadata for a single HTML report.

    Attributes:
        filename: The report filename, e.g. "GanttChart.html".
        title: Human-readable title extracted from the HTML, e.g. "Gantt Chart".
        filepath: Absolute path to the report file.
    """

    filename: str
    title: str
    filepath: Path


# Patterns for extracting titles from HTML content.
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
# Strip HTML tags from extracted text.
_TAG_RE = re.compile(r"<[^>]+>")


def _extract_title(html_content: str, filename: str) -> str:
    """Extract a human-readable title from HTML content.

    Tries <title> first, then the first <h1> element. Falls back to
    the filename without extension if neither can be parsed.

    Args:
        html_content: Raw HTML content of the report file.
        filename: The report filename, used as fallback.

    Returns:
        Extracted or fallback title string.
    """
    # Try <title> tag first.
    match = _TITLE_RE.search(html_content)
    if match:
        title = _TAG_RE.sub("", match.group(1)).strip()
        if title:
            return title

    # Try first <h1> tag.
    match = _H1_RE.search(html_content)
    if match:
        title = _TAG_RE.sub("", match.group(1)).strip()
        if title:
            return title

    # Fall back to filename without extension.
    return Path(filename).stem


def discover_reports(report_dir: Path) -> list[ReportInfo]:
    """Scan report directory for HTML files and extract titles.

    Discovers all `.html` files in the given directory (non-recursive),
    reads each file to extract a title from the ``<title>`` or first
    ``<h1>`` element, and returns a list of ReportInfo objects sorted
    alphabetically by filename.

    Args:
        report_dir: Path to the directory containing HTML report files.

    Returns:
        List of ReportInfo objects for each discovered HTML file,
        sorted by filename.
    """
    reports: list[ReportInfo] = []

    for html_file in sorted(report_dir.glob("*.html")):
        if not html_file.is_file():
            continue

        try:
            content = html_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            content = ""

        title = _extract_title(content, html_file.name)
        reports.append(
            ReportInfo(
                filename=html_file.name,
                title=title,
                filepath=html_file.resolve(),
            )
        )

    return reports


def _escape_html(text: str) -> str:
    """Escape HTML special characters in text.

    Args:
        text: Raw text to escape.

    Returns:
        HTML-safe string.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_nav_header(
    reports: list[ReportInfo],
    active_filename: str,
    admin_path: str = "../admin/",
) -> str:
    """Generate HTML navigation header with links to all reports and admin panel.

    Produces a ``<nav>`` element containing relative links to every report
    in the set, a link to the Report_Index (index.html), and a link to the
    admin panel. The link matching ``active_filename`` receives the CSS
    class ``nav-active``.

    Args:
        reports: All reports in the set.
        active_filename: The filename of the currently active report.
        admin_path: Relative path to admin panel.

    Returns:
        HTML string for the navigation header.
    """
    links: list[str] = []

    # Link to Report Index.
    index_class = ' class="nav-active"' if active_filename == "index.html" else ""
    links.append(f'<a href="index.html"{index_class}>{_escape_html("Report Index")}</a>')

    # Links to each report.
    for report in reports:
        if report.filename == active_filename:
            links.append(
                f'<a href="{_escape_html(report.filename)}" class="nav-active">'
                f"{_escape_html(report.title)}</a>"
            )
        else:
            links.append(
                f'<a href="{_escape_html(report.filename)}">'
                f"{_escape_html(report.title)}</a>"
            )

    # Link to admin panel.
    links.append(f'<a href="{_escape_html(admin_path)}">Admin</a>')

    nav_items = " | ".join(links)
    return f'<nav class="tj-nav-header">{nav_items}</nav>\n'


def generate_index(reports: list[ReportInfo], admin_path: str = "admin/") -> str:
    """Generate Report_Index HTML page listing all reports with links.

    Produces a complete HTML page with a list of all reports (title and
    relative link) and a link to the admin panel.

    Args:
        reports: All reports in the set.
        admin_path: Relative path to admin panel.

    Returns:
        Complete HTML string for the index page.
    """
    report_items: list[str] = []
    for report in reports:
        report_items.append(
            f'  <li><a href="{_escape_html(report.filename)}">'
            f"{_escape_html(report.title)}</a></li>"
        )

    report_list = "\n".join(report_items)

    # Generate the nav header for the index page itself.
    nav_header = generate_nav_header(reports, active_filename="index.html", admin_path=admin_path)

    return (
        "<!DOCTYPE html>\n"
        "<html>\n"
        "<head>\n"
        "  <meta charset=\"utf-8\">\n"
        "  <title>Report Index</title>\n"
        "</head>\n"
        "<body>\n"
        f"{nav_header}"
        "<h1>Report Index</h1>\n"
        "<ul>\n"
        f"{report_list}\n"
        "</ul>\n"
        f'<p><a href="{_escape_html(admin_path)}">Admin Panel</a></p>\n'
        "</body>\n"
        "</html>\n"
    )

# Pattern for matching <body> tag (case-insensitive, with optional attributes).
_BODY_RE = re.compile(r"(<body[^>]*>)", re.IGNORECASE)


def inject_nav_headers(report_dir: Path) -> int:
    """Main entry point: discover reports, inject nav headers, generate index.

    Scans the report directory for HTML files, injects a navigation header
    after the ``<body>`` tag in each report, and generates an ``index.html``
    page listing all reports.

    Args:
        report_dir: Path to the directory containing HTML report files.

    Returns:
        Number of reports processed.

    Raises:
        FileNotFoundError: If report_dir does not exist.
    """
    if not report_dir.exists():
        logger.error("Report directory does not exist: %s", report_dir)
        raise FileNotFoundError(f"Report directory does not exist: {report_dir}")

    if not report_dir.is_dir():
        logger.error("Report path is not a directory: %s", report_dir)
        raise NotADirectoryError(f"Report path is not a directory: {report_dir}")

    reports = discover_reports(report_dir)

    if not reports:
        logger.warning("No HTML report files found in %s", report_dir)

    # Inject navigation header into each discovered report.
    processed = 0
    for report in reports:
        nav_header = generate_nav_header(reports, active_filename=report.filename)

        try:
            content = report.filepath.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error("Cannot read report file %s: %s", report.filepath, exc)
            continue

        # Inject nav header after <body> tag (case-insensitive).
        match = _BODY_RE.search(content)
        if match:
            insert_pos = match.end()
            new_content = content[:insert_pos] + "\n" + nav_header + content[insert_pos:]
        else:
            # No <body> tag found — prepend nav header to the content.
            logger.warning("No <body> tag found in %s, prepending nav header", report.filename)
            new_content = nav_header + content

        try:
            report.filepath.write_text(new_content, encoding="utf-8")
            processed += 1
        except OSError as exc:
            logger.error("Cannot write to report file %s: %s", report.filepath, exc)
            continue

    # Generate and write the Report_Index page.
    index_content = generate_index(reports)
    index_path = report_dir / "index.html"
    try:
        index_path.write_text(index_content, encoding="utf-8")
        logger.info(
            "Generated index.html and processed %d report(s) in %s", processed, report_dir
        )
    except OSError as exc:
        logger.error("Cannot write index.html to %s: %s", report_dir, exc)

    return processed


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <report_directory>", file=sys.stderr)
        sys.exit(1)

    report_directory = Path(sys.argv[1])

    try:
        count = inject_nav_headers(report_directory)
        print(f"{count}")
    except (FileNotFoundError, NotADirectoryError) as exc:
        logger.error("%s", exc)
        sys.exit(1)
