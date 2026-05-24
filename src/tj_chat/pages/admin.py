"""Admin page with compilation trigger and system status.

Provides project administration controls including a rebuild button
that invokes the tj3 compiler and displays system health information.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import httpx
from nicegui import ui

from tj_chat.models import CompilerResult, SystemStatus
from tj_chat.settings import ChatSettings

logger = logging.getLogger(__name__)


class AdminPageUI:
    """Admin page with compilation trigger and system status.

    Displays system status (project file existence, report count,
    timesheet count, LM Studio connection) and provides a rebuild
    button that runs tj3 against the project.

    Args:
        project_dir: Path to the project directory.
        reports_dir: Path to the reports directory.
        settings: Chat settings for LM Studio URL and project file name.
    """

    def __init__(
        self,
        project_dir: Path,
        reports_dir: Path,
        settings: ChatSettings | None = None,
    ) -> None:
        self._project_dir = project_dir
        self._reports_dir = reports_dir
        self._settings = settings or ChatSettings()

    def setup(self) -> None:
        """Render the admin page UI components."""
        with ui.column().classes("w-full max-w-3xl mx-auto p-8 gap-6"):
            ui.label("Admin").classes("text-h4")

            # System status card
            with ui.card().classes("w-full"):
                ui.label("System Status").classes("text-h6")
                self._status_container = ui.column().classes("gap-2 mt-2")
                with self._status_container:
                    ui.label("Loading status...").classes("text-grey")

            # Rebuild section
            with ui.card().classes("w-full"):
                ui.label("Project Compilation").classes("text-h6")
                with ui.row().classes("items-center gap-4 mt-2"):
                    self._rebuild_button = ui.button(
                        "Rebuild",
                        on_click=self._trigger_rebuild,
                        icon="build",
                    ).props("color=primary")
                    self._spinner = ui.spinner(size="sm").classes("hidden")

                self._result_container = ui.column().classes("w-full mt-4")

        # Load initial status
        ui.timer(0.1, self._refresh_status, once=True)

    async def _trigger_rebuild(self) -> None:
        """Run tj3 compilation and display the result."""
        self._rebuild_button.disable()
        self._spinner.classes(remove="hidden")
        self._result_container.clear()

        try:
            result = await self._run_compiler()

            with self._result_container:
                if result.success:
                    report_count = self._count_reports()
                    ui.label(
                        f"✓ Compilation successful — {report_count} report(s) generated"
                    ).classes("text-positive text-bold")
                    if result.stdout.strip():
                        with ui.expansion("Compiler output").classes("w-full"):
                            ui.code(result.stdout.strip()).classes("w-full")
                    ui.notify(
                        f"Build successful: {report_count} report(s)",
                        type="positive",
                    )
                else:
                    ui.label("✗ Compilation failed").classes(
                        "text-negative text-bold"
                    )
                    error_text = result.stderr.strip() or result.stdout.strip()
                    if error_text:
                        ui.code(error_text).classes(
                            "w-full text-negative"
                        )
                    ui.notify("Build failed", type="negative")
        finally:
            self._rebuild_button.enable()
            self._spinner.classes(add="hidden")

        # Refresh status after rebuild
        await self._refresh_status()

    async def _refresh_status(self) -> None:
        """Refresh the system status display."""
        status = await self._get_status()
        self._status_container.clear()
        with self._status_container:
            _status_row(
                "Project file",
                self._settings.project_file,
                status.project_exists,
            )
            _status_row(
                "Reports",
                f"{status.report_count} report(s)",
                status.report_count > 0,
            )
            _status_row(
                "Timesheets",
                f"{status.timesheet_count} timesheet(s)",
                status.timesheet_count > 0,
            )
            _status_row(
                "LM Studio",
                self._settings.lm_studio_url,
                status.lm_studio_connected,
            )

    async def _get_status(self) -> SystemStatus:
        """Gather current system status information.

        Returns:
            SystemStatus with project file existence, report count,
            timesheet count, and LM Studio connectivity.
        """
        project_file_path = self._project_dir / self._settings.project_file
        project_exists = project_file_path.exists()
        report_count = self._count_reports()
        timesheet_count = self._count_timesheets()
        lm_connected = await self._check_lm_studio()

        return SystemStatus(
            project_file=self._settings.project_file,
            project_exists=project_exists,
            report_count=report_count,
            timesheet_count=timesheet_count,
            lm_studio_connected=lm_connected,
        )

    def _count_reports(self) -> int:
        """Count HTML report files in the reports directory."""
        if not self._reports_dir.exists():
            return 0
        return len(list(self._reports_dir.glob("*.html")))

    def _count_timesheets(self) -> int:
        """Count timesheet files in the project timesheets directory."""
        timesheets_dir = self._project_dir / "timesheets"
        if not timesheets_dir.exists():
            return 0
        return len(list(timesheets_dir.glob("*.tji")))

    async def _check_lm_studio(self) -> bool:
        """Check if LM Studio is reachable at the configured URL.

        Returns:
            True if the models endpoint responds successfully.
        """
        try:
            async with httpx.AsyncClient(
                timeout=self._settings.connection_timeout
            ) as client:
                response = await client.get(
                    f"{self._settings.lm_studio_url}/models"
                )
                return response.status_code == 200
        except Exception:
            return False

    async def _run_compiler(self) -> CompilerResult:
        """Run the tj3 compiler against the project file.

        Returns:
            CompilerResult with success status and compiler output.
        """
        project_file = self._project_dir / self._settings.project_file
        if not project_file.exists():
            return CompilerResult(
                success=False,
                stdout="",
                stderr=f"Project file not found: {self._settings.project_file}",
            )

        try:
            process = await asyncio.create_subprocess_exec(
                "tj3",
                str(project_file),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._project_dir),
            )
            stdout_bytes, stderr_bytes = await process.communicate()
            return CompilerResult(
                success=process.returncode == 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
            )
        except FileNotFoundError:
            return CompilerResult(
                success=False,
                stdout="",
                stderr="tj3 compiler not found. Ensure TaskJuggler is installed.",
            )


def _status_row(label: str, detail: str, ok: bool) -> None:
    """Render a single status row with an indicator icon.

    Args:
        label: The status item label.
        detail: Additional detail text.
        ok: Whether the status is healthy (True) or not (False).
    """
    icon = "check_circle" if ok else "cancel"
    color = "text-positive" if ok else "text-negative"
    with ui.row().classes("items-center gap-2"):
        ui.icon(icon).classes(color)
        ui.label(f"{label}:").classes("font-bold")
        ui.label(detail)
