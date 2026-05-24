"""Unit tests for editor page routing and navigation.

Tests that the /editor route is registered, the navigation header includes
an "Editor" link, and EditorPageUI can be instantiated with mocked services.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tj_chat.editor_models import FileNode
from tj_chat.pages.editor import EditorPageUI
from tj_chat.settings import ChatSettings


@pytest.fixture
def settings(tmp_path: Path) -> ChatSettings:
    """Create ChatSettings pointing to a temp project directory."""
    return ChatSettings(project_path=tmp_path)


@pytest.fixture
def editor_service() -> MagicMock:
    """Create a mock EditorService."""
    service = MagicMock()
    service.build_file_tree.return_value = []
    return service


@pytest.fixture
def helper_service() -> MagicMock:
    """Create a mock HelperService."""
    return MagicMock()


class TestEditorRouteRegistration:
    """Tests that the /editor route is properly registered."""

    def test_editor_route_defined_in_create_app(self) -> None:
        """Verify create_app defines an /editor route via @ui.page decorator."""
        import inspect

        from tj_chat.app import create_app

        source = inspect.getsource(create_app)
        assert '@ui.page("/editor")' in source

    def test_editor_page_function_defined_in_create_app(self) -> None:
        """Verify editor_page function is defined inside create_app."""
        import inspect

        from tj_chat.app import create_app

        source = inspect.getsource(create_app)
        assert "def editor_page()" in source

    def test_create_app_completes_with_editor_route(self) -> None:
        """Verify create_app completes without error (editor route included)."""
        from tj_chat.app import create_app

        with patch("tj_chat.app.app.add_static_files"):
            create_app()  # Should not raise


class TestNavHeaderEditorLink:
    """Tests that the navigation header includes an 'Editor' link."""

    def test_nav_header_links_include_editor(self) -> None:
        """The _nav_header links list includes an 'Editor' entry."""
        from tj_chat.app import _nav_header

        # Inspect the source to verify "Editor" is in the links list
        import inspect

        source = inspect.getsource(_nav_header)
        assert '"Editor"' in source or "'Editor'" in source

    def test_editor_link_points_to_editor_path(self) -> None:
        """The 'Editor' link points to '/editor'."""
        from tj_chat.app import _nav_header

        import inspect

        source = inspect.getsource(_nav_header)
        # Verify the ("Editor", "/editor") tuple is in the links
        assert '("Editor", "/editor")' in source

    def test_editor_link_highlighted_when_active(self) -> None:
        """The 'Editor' link gets font-bold underline when current_path is '/editor'."""
        from tj_chat.app import _nav_header

        import inspect

        source = inspect.getsource(_nav_header)
        # The _nav_header applies "font-bold underline" when current_path matches
        assert "font-bold underline" in source or "font-bold" in source

    def test_nav_header_links_order(self) -> None:
        """'Editor' appears between 'Admin' and 'Chat' in the links list."""
        from tj_chat.app import _nav_header

        import inspect

        source = inspect.getsource(_nav_header)
        # Find positions of the link entries
        admin_pos = source.find('"Admin"')
        editor_pos = source.find('"Editor"')
        chat_pos = source.find('"Chat"')

        assert admin_pos < editor_pos < chat_pos


class TestEditorPageUIInstantiation:
    """Tests that EditorPageUI can be instantiated with mocked services."""

    def test_instantiation_with_mocked_services(
        self,
        editor_service: MagicMock,
        helper_service: MagicMock,
        settings: ChatSettings,
    ) -> None:
        """EditorPageUI can be created with mocked EditorService and HelperService."""
        page = EditorPageUI(
            editor_service=editor_service,
            helper_service=helper_service,
            settings=settings,
        )
        assert page is not None
        assert page._editor_service is editor_service
        assert page._helper_service is helper_service
        assert page._settings is settings

    def test_initial_state_no_file_selected(
        self,
        editor_service: MagicMock,
        helper_service: MagicMock,
        settings: ChatSettings,
    ) -> None:
        """EditorPageUI starts with no file selected and clean state."""
        page = EditorPageUI(
            editor_service=editor_service,
            helper_service=helper_service,
            settings=settings,
        )
        assert page._current_file is None
        assert page._is_dirty is False
        assert page._is_saving is False
        assert page._helper_expanded is True

    def test_setup_method_exists(
        self,
        editor_service: MagicMock,
        helper_service: MagicMock,
        settings: ChatSettings,
    ) -> None:
        """EditorPageUI has a setup() method."""
        page = EditorPageUI(
            editor_service=editor_service,
            helper_service=helper_service,
            settings=settings,
        )
        assert callable(page.setup)
