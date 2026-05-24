"""Home page component displaying project status summary.

Shows report count, timesheet count, project file status, and a link
to the chat page.
"""

from __future__ import annotations

from pathlib import Path

from nicegui import ui

from tj_chat.settings import ChatSettings


class HomePageUI:
    """Renders the home page with project status summary.

    Displays:
    - Project name and status
    - Number of available reports
    - Number of timesheet files
    - Whether the main project file exists
    - Link to the chat page
    """

    def __init__(self, settings: ChatSettings) -> None:
        """Initialize with application settings.

        Args:
            settings: Application configuration providing paths and project file name.
        """
        self._settings = settings
        self._project_path: Path = settings.project_path
        self._reports_path: Path = settings.reports_path
        self._project_file: str = settings.project_file

    def setup(self) -> None:
        """Render the home page content using NiceGUI components."""
        project_exists = self._check_project_file()
        report_count = self._count_reports()
        timesheet_count = self._count_timesheets()

        with ui.column().classes("w-full items-center p-8 gap-4"):
            ui.label("tjallin").classes("text-h4 font-bold")
            ui.label("Project Status").classes("text-h5 text-grey-8")

            with ui.card().classes("w-full max-w-md"):
                with ui.column().classes("w-full gap-2"):
                    # Project file status
                    status_icon = "✓" if project_exists else "✗"
                    status_color = "text-positive" if project_exists else "text-negative"
                    ui.label(
                        f"{status_icon} Project file: {self._project_file}"
                    ).classes(status_color)

                    # Report count
                    ui.label(f"📊 Reports: {report_count}")

                    # Timesheet count
                    ui.label(f"📅 Timesheets: {timesheet_count}")

            # Link to chat
            ui.link("Open Chat →", "/chat").classes(
                "text-lg mt-4 text-primary font-medium"
            )

    def _check_project_file(self) -> bool:
        """Check whether the main project file exists.

        Returns:
            True if the project .tjp file exists, False otherwise.
        """
        return (self._project_path / self._project_file).is_file()

    def _count_reports(self) -> int:
        """Count HTML report files in the reports directory.

        Returns:
            Number of .html files found, or 0 if directory doesn't exist.
        """
        if not self._reports_path.is_dir():
            return 0
        return len(list(self._reports_path.glob("**/*.html")))

    def _count_timesheets(self) -> int:
        """Count timesheet files in the project timesheets directory.

        Timesheets follow the naming convention YYYY-Www-<resource_id>.tji
        and are stored in a timesheets subdirectory.

        Returns:
            Number of .tji files in the timesheets directory, or 0 if missing.
        """
        timesheets_dir = self._project_path / "timesheets"
        if not timesheets_dir.is_dir():
            return 0
        return len(list(timesheets_dir.glob("*.tji")))
