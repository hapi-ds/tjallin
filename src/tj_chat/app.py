"""NiceGUI application entry point with page routing and shared navigation.

Provides the unified web interface for the tjallin system, consolidating
report viewing, project administration, and agent chat into a single app.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from nicegui import app, ui

from tj_chat.pages.admin import AdminPageUI
from tj_chat.pages.chat import ChatPageUI
from tj_chat.pages.home import HomePageUI
from tj_chat.pages.reports import ReportsPageUI
from tj_chat.settings import ChatSettings

if TYPE_CHECKING:
    from tj_chat.chat_service import ChatService
    from tj_chat.tj_docs import TJDocumentationService

logger = logging.getLogger(__name__)


def _nav_header() -> None:
    """Render the shared navigation header used across all pages."""
    with ui.header().classes("items-center justify-between"):
        ui.label("tjallin").classes("text-h6 font-bold")
        with ui.row().classes("gap-4"):
            ui.link("Home", "/").classes("text-white")
            ui.link("Reports", "/reports").classes("text-white")
            ui.link("Admin", "/admin").classes("text-white")
            ui.link("Chat", "/chat").classes("text-white")


def create_app() -> None:
    """Configure and create the NiceGUI application.

    Sets up page routing for home, reports, admin, and chat pages.
    Configures static file serving for the reports volume.
    """
    settings = ChatSettings()

    # Serve generated HTML reports as static files
    app.add_static_files("/report-files", str(settings.reports_path))

    # Lazy-initialize shared services for the chat page
    _chat_service_holder: dict = {}

    def _get_chat_service() -> "ChatService":
        """Get or create the shared ChatService instance."""
        from tj_chat.chat_service import ChatService
        from tj_chat.project_reader import ProjectReader
        from tj_chat.tool_executor import ToolExecutor

        if "service" not in _chat_service_holder:
            tool_executor = ToolExecutor(
                project_dir=settings.project_path,
                settings=settings,
            )
            service = ChatService(
                settings=settings,
                tool_executor=tool_executor,
            )
            # Attach TJ docs service to both chat service and tool executor
            from tj_chat.tj_docs import TJDocumentationService

            tj_docs = TJDocumentationService(settings.tj_docs_path)
            service.tj_docs = tj_docs
            tool_executor.tj_docs = tj_docs

            # Build and set the system prompt with project context
            reader = ProjectReader(settings.project_path)
            project_summary = reader.get_project_summary()
            service.set_system_prompt(project_summary)

            _chat_service_holder["service"] = service
            _chat_service_holder["tj_docs"] = tj_docs
        return _chat_service_holder["service"]

    def _get_tj_docs() -> "TJDocumentationService | None":
        """Get the TJ documentation service instance."""
        # Ensure chat service is initialized (which also creates tj_docs)
        _get_chat_service()
        return _chat_service_holder.get("tj_docs")

    @ui.page("/")
    def home_page() -> None:
        """Home page with project status summary."""
        _nav_header()
        page = HomePageUI(settings=settings)
        page.setup()

    @ui.page("/reports")
    def reports_page() -> None:
        """Reports page listing TaskJuggler-generated HTML reports."""
        _nav_header()
        page = ReportsPageUI(reports_dir=settings.reports_path)
        page.setup()

    @ui.page("/admin")
    def admin_page() -> None:
        """Admin page with compilation triggers and system status."""
        _nav_header()
        page = AdminPageUI(
            project_dir=settings.project_path,
            reports_dir=settings.reports_path,
            settings=settings,
        )
        page.setup()

    @ui.page("/chat")
    def chat_page() -> None:
        """Chat page with the LLM agent conversational interface."""
        _nav_header()
        chat_service = _get_chat_service()
        tj_docs = _get_tj_docs()
        page = ChatPageUI(chat_service=chat_service, tj_docs=tj_docs)
        page.setup()


def main() -> None:
    """Application entry point. Configures and starts the NiceGUI server."""
    settings = ChatSettings()
    create_app()
    ui.run(
        title="tjallin",
        port=settings.web_port,
        reload=False,
    )
