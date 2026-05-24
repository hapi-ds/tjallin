"""Unit tests for EditorPageUI file tree component.

Tests the file tree data building, icon assignment, directory detection,
and file loading logic implemented in task 8.2.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tj_chat.editor_models import FileContent, FileNode
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
    service.build_file_tree.return_value = [
        FileNode(
            name="subdir",
            path="subdir",
            is_directory=True,
            children=[
                FileNode(
                    name="nested.tji",
                    path="subdir/nested.tji",
                    is_directory=False,
                    file_type="tji",
                ),
            ],
            file_type="other",
        ),
        FileNode(
            name="project.tjp",
            path="project.tjp",
            is_directory=False,
            file_type="tjp",
        ),
        FileNode(
            name="tasks.tji",
            path="tasks.tji",
            is_directory=False,
            file_type="tji",
        ),
        FileNode(
            name="readme.md",
            path="readme.md",
            is_directory=False,
            file_type="other",
        ),
    ]
    service.read_file = AsyncMock()
    return service


@pytest.fixture
def helper_service() -> MagicMock:
    """Create a mock HelperService."""
    return MagicMock()


@pytest.fixture
def page(
    editor_service: MagicMock,
    helper_service: MagicMock,
    settings: ChatSettings,
) -> EditorPageUI:
    """Create an EditorPageUI instance with mocked services."""
    return EditorPageUI(
        editor_service=editor_service,
        helper_service=helper_service,
        settings=settings,
    )


class TestBuildTreeData:
    """Tests for EditorPageUI._build_tree_data()."""

    def test_converts_file_nodes_to_tree_format(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """_build_tree_data converts FileNode list to NiceGUI tree format."""
        nodes = editor_service.build_file_tree()
        result = page._build_tree_data(nodes)

        assert isinstance(result, list)
        assert len(result) == 4

    def test_directory_node_has_children_key(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """Directory nodes include a 'children' key in the output."""
        nodes = editor_service.build_file_tree()
        result = page._build_tree_data(nodes)

        dir_node = result[0]
        assert dir_node["id"] == "subdir"
        assert dir_node["label"] == "subdir"
        assert "children" in dir_node
        assert len(dir_node["children"]) == 1

    def test_file_node_has_no_children_key(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """File nodes do not include a 'children' key."""
        nodes = editor_service.build_file_tree()
        result = page._build_tree_data(nodes)

        file_node = result[1]  # project.tjp
        assert file_node["id"] == "project.tjp"
        assert "children" not in file_node

    def test_empty_directory_has_empty_children(
        self, page: EditorPageUI
    ) -> None:
        """Empty directories get an empty children list."""
        nodes = [
            FileNode(
                name="empty_dir",
                path="empty_dir",
                is_directory=True,
                children=[],
                file_type="other",
            ),
        ]
        result = page._build_tree_data(nodes)

        assert result[0]["children"] == []

    def test_nested_children_converted_recursively(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """Nested children are converted recursively."""
        nodes = editor_service.build_file_tree()
        result = page._build_tree_data(nodes)

        nested = result[0]["children"][0]
        assert nested["id"] == "subdir/nested.tji"
        assert nested["label"] == "nested.tji"
        assert nested["icon"] == "code"


class TestGetNodeIcon:
    """Tests for EditorPageUI._get_node_icon()."""

    def test_directory_gets_folder_icon(self, page: EditorPageUI) -> None:
        """Directories use the 'folder' icon."""
        node = FileNode(
            name="dir", path="dir", is_directory=True, file_type="other"
        )
        assert page._get_node_icon(node) == "folder"

    def test_tjp_file_gets_star_icon(self, page: EditorPageUI) -> None:
        """.tjp files use the 'star' icon."""
        node = FileNode(
            name="project.tjp",
            path="project.tjp",
            is_directory=False,
            file_type="tjp",
        )
        assert page._get_node_icon(node) == "star"

    def test_tji_file_gets_code_icon(self, page: EditorPageUI) -> None:
        """.tji files use the 'code' icon."""
        node = FileNode(
            name="tasks.tji",
            path="tasks.tji",
            is_directory=False,
            file_type="tji",
        )
        assert page._get_node_icon(node) == "code"

    def test_other_file_gets_description_icon(
        self, page: EditorPageUI
    ) -> None:
        """Other files use the 'description' icon."""
        node = FileNode(
            name="readme.md",
            path="readme.md",
            is_directory=False,
            file_type="other",
        )
        assert page._get_node_icon(node) == "description"


class TestIsDirectoryNode:
    """Tests for EditorPageUI._is_directory_node()."""

    def test_directory_path_returns_true(
        self, page: EditorPageUI
    ) -> None:
        """A known directory path returns True."""
        assert page._is_directory_node("subdir") is True

    def test_file_path_returns_false(
        self, page: EditorPageUI
    ) -> None:
        """A known file path returns False."""
        assert page._is_directory_node("project.tjp") is False

    def test_nested_file_returns_false(
        self, page: EditorPageUI
    ) -> None:
        """A nested file path returns False."""
        assert page._is_directory_node("subdir/nested.tji") is False

    def test_unknown_path_returns_false(
        self, page: EditorPageUI
    ) -> None:
        """An unknown path returns False."""
        assert page._is_directory_node("nonexistent.txt") is False


class TestOnFileSelect:
    """Tests for EditorPageUI._on_file_select()."""

    @pytest.mark.asyncio
    async def test_none_selection_does_nothing(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """None selection is ignored."""
        await page._on_file_select(None)
        editor_service.read_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_directory_selection_does_nothing(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """Selecting a directory does not trigger file load."""
        await page._on_file_select("subdir")
        editor_service.read_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_file_selection_loads_file(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """Selecting a file triggers file load when not dirty."""
        page._is_dirty = False

        with patch.object(
            page, "load_file", new_callable=AsyncMock
        ) as mock_load:
            await page._on_file_select("project.tjp")

        mock_load.assert_called_once_with("project.tjp")

    @pytest.mark.asyncio
    async def test_dirty_file_triggers_confirm_dialog(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """Selecting a file when dirty triggers confirmation dialog."""
        page._is_dirty = True

        with patch.object(
            page, "_confirm_discard_and_load", new_callable=AsyncMock
        ) as mock_confirm:
            await page._on_file_select("project.tjp")

        mock_confirm.assert_called_once_with("project.tjp")


class TestLoadFile:
    """Tests for EditorPageUI.load_file()."""

    @pytest.fixture(autouse=True)
    def _setup_ui_mocks(self, page: EditorPageUI) -> None:
        """Set up mock UI elements that load_file accesses."""
        page._file_path_label = MagicMock()
        page._placeholder = MagicMock()
        page._editor_container = MagicMock()
        page._editor = None
        page._save_button = MagicMock()
        page._error_panel = MagicMock()

    @pytest.mark.asyncio
    async def test_successful_load_updates_state(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """Successful file load updates current_file and clears dirty flag."""
        editor_service.read_file.return_value = FileContent(
            path="project.tjp",
            content="project content",
            success=True,
        )
        page._is_dirty = True

        with patch("tj_chat.pages.editor.ui"):
            await page.load_file("project.tjp")

        assert page._current_file == "project.tjp"
        assert page._is_dirty is False

    @pytest.mark.asyncio
    async def test_failed_load_shows_notification(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """Failed file load shows error notification and retains state."""
        editor_service.read_file.return_value = FileContent(
            path="bad.tjp",
            content="",
            success=False,
            error="Permission denied",
        )
        page._current_file = "old_file.tjp"

        with patch("tj_chat.pages.editor.ui") as mock_ui:
            await page.load_file("bad.tjp")

        # Current file should not change on failure
        assert page._current_file == "old_file.tjp"
        mock_ui.notify.assert_called_once()
        call_kwargs = mock_ui.notify.call_args
        assert "Permission denied" in call_kwargs[0][0]
        assert call_kwargs[1]["type"] == "negative"

    @pytest.mark.asyncio
    async def test_load_calls_editor_service_read(
        self, page: EditorPageUI, editor_service: MagicMock
    ) -> None:
        """load_file calls editor_service.read_file with the path."""
        editor_service.read_file.return_value = FileContent(
            path="tasks.tji",
            content="content",
            success=True,
        )

        with patch("tj_chat.pages.editor.ui"):
            await page.load_file("tasks.tji")

        editor_service.read_file.assert_called_once_with("tasks.tji")
