"""Reports page listing and displaying TaskJuggler-generated HTML reports.

Scans the reports volume for .html files and presents them as a navigable
list with links to view each report via the static file endpoint.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from nicegui import ui

from tj_chat.models import ReportFile

logger = logging.getLogger(__name__)


class ReportsPageUI:
    """Reports page listing and displaying TJ-generated HTML reports.

    Scans the configured reports directory for .html files and renders
    a list with links to view each report. Shows a helpful message when
    no reports are available.
    """

    def __init__(self, reports_dir: Path) -> None:
        """Initialize the reports page.

        Args:
            reports_dir: Path to the directory containing generated HTML reports.
        """
        self.reports_dir = reports_dir

    def setup(self) -> None:
        """Render the reports page UI."""
        with ui.column().classes("w-full max-w-4xl mx-auto p-8"):
            ui.label("Reports").classes("text-h4 q-mb-md")

            reports = self.list_reports()

            if not reports:
                self._display_empty_state()
            else:
                self._display_report_list(reports)

    def list_reports(self) -> list[ReportFile]:
        """Scan the reports directory for available HTML report files.

        Returns:
            List of ReportFile objects sorted by modification time (newest first).
        """
        if not self.reports_dir.exists():
            logger.warning("Reports directory does not exist: %s", self.reports_dir)
            return []

        report_files: list[ReportFile] = []
        for file_path in sorted(self.reports_dir.glob("*.html")):
            if not file_path.is_file():
                continue
            stat = file_path.stat()
            modified_dt = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            report_files.append(
                ReportFile(
                    name=file_path.name,
                    path=f"/report-files/{file_path.name}",
                    size=stat.st_size,
                    modified=modified_dt.strftime("%Y-%m-%d %H:%M"),
                )
            )

        # Sort by modification time, newest first
        report_files.sort(key=lambda r: r.modified, reverse=True)
        return report_files

    def _display_empty_state(self) -> None:
        """Display a helpful message when no reports are available."""
        with ui.card().classes("w-full q-pa-lg"):
            ui.icon("description", size="xl").classes("text-grey-5 q-mb-sm")
            ui.label("No reports available").classes("text-h6 text-grey-7")
            ui.label(
                "Reports are generated when the project is compiled. "
                "Use the Admin page to trigger a rebuild."
            ).classes("text-body1 text-grey-6 q-mt-sm")
            ui.link("Go to Admin to rebuild reports", "/admin").classes(
                "q-mt-md text-primary"
            )

    def _display_report_list(self, reports: list[ReportFile]) -> None:
        """Display the list of available reports.

        Args:
            reports: List of ReportFile objects to display.
        """
        ui.label(f"{len(reports)} report(s) available").classes(
            "text-body1 text-grey-7 q-mb-md"
        )

        for report in reports:
            with ui.card().classes("w-full q-mb-sm"):
                with ui.row().classes("items-center justify-between w-full"):
                    with ui.column().classes("gap-0"):
                        ui.link(
                            report.name,
                            report.path,
                            new_tab=True,
                        ).classes("text-body1 font-medium")
                        ui.label(
                            f"Modified: {report.modified} · "
                            f"Size: {_format_size(report.size)}"
                        ).classes("text-caption text-grey-6")
                    ui.link(
                        "Open ↗",
                        report.path,
                        new_tab=True,
                    ).classes("text-primary")


def _format_size(size_bytes: int) -> str:
    """Format a file size in bytes to a human-readable string.

    Args:
        size_bytes: File size in bytes.

    Returns:
        Human-readable size string (e.g., "1.2 KB", "3.4 MB").
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
