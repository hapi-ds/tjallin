"""Unit tests for the EditorPageUI helper panel functionality (task 8.4)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tj_chat.editor_models import DiffSuggestion, EditorContext, HelperResponse


def _make_page():
    """Create an EditorPageUI instance with mocked services."""
    from tj_chat.pages.editor import EditorPageUI

    mock_editor_service = MagicMock()
    mock_helper_service = MagicMock()
    mock_settings = MagicMock()

    page = EditorPageUI(
        editor_service=mock_editor_service,
        helper_service=mock_helper_service,
        settings=mock_settings,
    )
    return page


def _setup_helper_ui(page):
    """Mock the UI elements that the helper panel methods interact with."""
    page._helper_input = MagicMock()
    page._helper_spinner_row = MagicMock()
    page._helper_send_btn = MagicMock()
    page._helper_content = MagicMock()
    page._helper_scroll = MagicMock()
    page._helper_body = MagicMock()
    page._helper_toggle = MagicMock()
    page._file_path_label = MagicMock()
    page._file_path_label.text = "test.tjp"
    page._editor = MagicMock()
    page._editor.value = "line1\nline2\nline3\n"
    page._current_file = "test.tjp"


class TestToggleHelper:
    """Tests for _toggle_helper method."""

    def test_toggle_collapses_when_expanded(self) -> None:
        """Verify toggling from expanded hides the body and changes icon."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_expanded = True

        page._toggle_helper()

        assert page._helper_expanded is False
        page._helper_body.set_visibility.assert_called_with(False)
        page._helper_toggle.props.assert_called_with("icon=chevron_left")

    def test_toggle_expands_when_collapsed(self) -> None:
        """Verify toggling from collapsed shows the body and changes icon."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_expanded = False

        page._toggle_helper()

        assert page._helper_expanded is True
        page._helper_body.set_visibility.assert_called_with(True)
        page._helper_toggle.props.assert_called_with("icon=chevron_right")


class TestOnHelperSend:
    """Tests for _on_helper_send method."""

    def test_empty_input_does_nothing(self) -> None:
        """Verify empty input is rejected without calling helper service."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_input.value = ""

        asyncio.run(page._on_helper_send())

        page._helper_service.send_message.assert_not_called()

    def test_whitespace_only_input_does_nothing(self) -> None:
        """Verify whitespace-only input is rejected."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_input.value = "   \t\n  "

        asyncio.run(page._on_helper_send())

        page._helper_service.send_message.assert_not_called()

    def test_none_input_does_nothing(self) -> None:
        """Verify None input is rejected."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_input.value = None

        asyncio.run(page._on_helper_send())

        page._helper_service.send_message.assert_not_called()

    @patch("tj_chat.pages.editor.ui")
    def test_valid_input_calls_helper_service(self, mock_ui) -> None:
        """Verify valid input calls helper_service.send_message."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_input.value = "How do I define a task?"

        # Mock the helper service response
        page._helper_service.send_message = AsyncMock(
            return_value=HelperResponse(text="Use the task keyword.", suggestions=[])
        )

        # Mock context managers for UI elements
        mock_ui.row.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.row.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.chat_message = MagicMock()

        asyncio.run(page._on_helper_send())

        page._helper_service.send_message.assert_called_once()
        # Verify the message was stripped and passed
        call_args = page._helper_service.send_message.call_args
        assert call_args[0][0] == "How do I define a task?"
        assert isinstance(call_args[0][1], EditorContext)

    @patch("tj_chat.pages.editor.ui")
    def test_loading_state_during_request(self, mock_ui) -> None:
        """Verify loading indicator is shown during request and hidden after."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_input.value = "test question"

        page._helper_service.send_message = AsyncMock(
            return_value=HelperResponse(text="response", suggestions=[])
        )

        mock_ui.row.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.row.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.chat_message = MagicMock()

        asyncio.run(page._on_helper_send())

        # After completion, loading should be False
        assert page._helper_loading is False
        # Spinner should be hidden (classes add="hidden" called)
        page._helper_spinner_row.classes.assert_any_call(add="hidden")

    @patch("tj_chat.pages.editor.ui")
    def test_error_response_displays_error(self, mock_ui) -> None:
        """Verify error response from helper service is displayed inline."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_input.value = "test question"

        page._helper_service.send_message = AsyncMock(
            return_value=HelperResponse(
                text="",
                suggestions=[],
                error="The LLM service is unavailable.",
            )
        )

        mock_ui.row.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.row.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.card.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.card.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.chat_message = MagicMock()
        mock_ui.icon = MagicMock(return_value=MagicMock(classes=MagicMock()))
        mock_ui.label = MagicMock(return_value=MagicMock(classes=MagicMock()))
        mock_ui.button = MagicMock(return_value=MagicMock(props=MagicMock()))

        asyncio.run(page._on_helper_send())

        # Verify error was added to conversation
        assert any(
            msg["role"] == "error" for msg in page._conversation
        )

    @patch("tj_chat.pages.editor.ui")
    def test_exception_displays_error(self, mock_ui) -> None:
        """Verify unexpected exception is caught and displayed as error."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_input.value = "test question"

        page._helper_service.send_message = AsyncMock(
            side_effect=RuntimeError("Network failure")
        )

        mock_ui.row.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.row.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.card.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.card.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.chat_message = MagicMock()
        mock_ui.icon = MagicMock(return_value=MagicMock(classes=MagicMock()))
        mock_ui.label = MagicMock(return_value=MagicMock(classes=MagicMock()))
        mock_ui.button = MagicMock(return_value=MagicMock(props=MagicMock()))

        asyncio.run(page._on_helper_send())

        # Should not raise, and loading should be reset
        assert page._helper_loading is False
        assert any(
            msg["role"] == "error" and "Network failure" in msg["content"]
            for msg in page._conversation
        )

    def test_blocked_while_loading(self) -> None:
        """Verify send is blocked while a request is in progress."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_input.value = "test"
        page._helper_loading = True

        asyncio.run(page._on_helper_send())

        page._helper_service.send_message.assert_not_called()

    @patch("tj_chat.pages.editor.ui")
    def test_input_cleared_after_send(self, mock_ui) -> None:
        """Verify input field is cleared after sending."""
        page = _make_page()
        _setup_helper_ui(page)
        page._helper_input.value = "my question"

        page._helper_service.send_message = AsyncMock(
            return_value=HelperResponse(text="answer", suggestions=[])
        )

        mock_ui.row.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.row.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.chat_message = MagicMock()

        asyncio.run(page._on_helper_send())

        assert page._helper_input.value == ""


class TestBuildEditorContext:
    """Tests for _build_editor_context method."""

    def test_context_includes_file_path(self) -> None:
        """Verify context includes the current file path."""
        page = _make_page()
        _setup_helper_ui(page)
        page._current_file = "project/main.tjp"
        page._editor_service.build_file_tree.return_value = []

        context = page._build_editor_context()

        assert context.file_path == "project/main.tjp"

    def test_context_includes_file_content(self) -> None:
        """Verify context includes the editor content."""
        page = _make_page()
        _setup_helper_ui(page)
        page._editor.value = "task foo { }"
        page._editor_service.build_file_tree.return_value = []

        context = page._build_editor_context()

        assert context.file_content == "task foo { }"

    def test_context_with_no_editor(self) -> None:
        """Verify context works when no editor is loaded."""
        page = _make_page()
        _setup_helper_ui(page)
        page._editor = None
        page._current_file = None
        page._editor_service.build_file_tree.return_value = []

        context = page._build_editor_context()

        assert context.file_path is None
        assert context.file_content == ""
        assert context.cursor_line == 0

    def test_context_includes_project_files(self) -> None:
        """Verify context includes project file list from editor service."""
        from tj_chat.editor_models import FileNode

        page = _make_page()
        _setup_helper_ui(page)
        file_nodes = [
            FileNode(name="main.tjp", path="main.tjp", is_directory=False, file_type="tjp"),
            FileNode(name="includes", path="includes", is_directory=True, children=[
                FileNode(name="resources.tji", path="includes/resources.tji", is_directory=False, file_type="tji"),
            ]),
        ]
        page._editor_service.build_file_tree.return_value = file_nodes
        # Update the cached nodes (normally populated during __init__)
        page._cached_file_nodes = file_nodes

        context = page._build_editor_context()

        assert "main.tjp" in context.project_files
        assert "includes/resources.tji" in context.project_files


class TestAcceptSuggestion:
    """Tests for _accept_suggestion method."""

    @patch("tj_chat.pages.editor.ui")
    def test_accept_applies_suggestion_to_editor(self, mock_ui) -> None:
        """Verify accepting a suggestion updates editor content."""
        page = _make_page()
        _setup_helper_ui(page)
        page._editor.value = "line1\nline2\nline3"

        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=2,
            end_line=2,
            original_content="line2",
            suggested_content="new_line2",
            status="pending",
        )

        mock_card = MagicMock()
        mock_btn_row = MagicMock()
        mock_ui.label = MagicMock(return_value=MagicMock(classes=MagicMock()))

        asyncio.run(page._accept_suggestion(suggestion, mock_card, mock_btn_row))

        assert page._editor.value == "line1\nnew_line2\nline3"
        assert suggestion.status == "accepted"
        assert page._is_dirty is True

    @patch("tj_chat.pages.editor.ui")
    def test_accept_outdated_suggestion_marks_outdated(self, mock_ui) -> None:
        """Verify accepting an outdated suggestion marks it as outdated."""
        page = _make_page()
        _setup_helper_ui(page)
        page._editor.value = "line1\nmodified_line2\nline3"

        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=2,
            end_line=2,
            original_content="line2",  # Doesn't match current content
            suggested_content="new_line2",
            status="pending",
        )

        mock_card = MagicMock()
        mock_btn_row = MagicMock()
        mock_ui.icon = MagicMock(return_value=MagicMock(classes=MagicMock()))
        mock_ui.label = MagicMock(return_value=MagicMock(classes=MagicMock()))

        asyncio.run(page._accept_suggestion(suggestion, mock_card, mock_btn_row))

        # Editor content should be unchanged
        assert page._editor.value == "line1\nmodified_line2\nline3"
        assert suggestion.status == "outdated"

    @patch("tj_chat.pages.editor.ui")
    def test_accept_already_accepted_does_nothing(self, mock_ui) -> None:
        """Verify accepting an already-accepted suggestion is a no-op."""
        page = _make_page()
        _setup_helper_ui(page)
        original_content = page._editor.value

        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=1,
            end_line=1,
            original_content="line1",
            suggested_content="new",
            status="accepted",
        )

        mock_card = MagicMock()
        mock_btn_row = MagicMock()

        asyncio.run(page._accept_suggestion(suggestion, mock_card, mock_btn_row))

        assert page._editor.value == original_content


class TestRejectSuggestion:
    """Tests for _reject_suggestion method."""

    @patch("tj_chat.pages.editor.ui")
    def test_reject_marks_suggestion_rejected(self, mock_ui) -> None:
        """Verify rejecting a suggestion marks it as rejected."""
        page = _make_page()
        _setup_helper_ui(page)

        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=1,
            end_line=1,
            original_content="line1",
            suggested_content="new",
            status="pending",
        )

        mock_card = MagicMock()
        mock_btn_row = MagicMock()
        mock_ui.label = MagicMock(return_value=MagicMock(classes=MagicMock()))

        page._reject_suggestion(suggestion, mock_card, mock_btn_row)

        assert suggestion.status == "rejected"
        # Card should get rejected styling
        mock_card.classes.assert_any_call(add="border-grey-300 bg-grey-100 opacity-60")

    @patch("tj_chat.pages.editor.ui")
    def test_reject_already_rejected_does_nothing(self, mock_ui) -> None:
        """Verify rejecting an already-rejected suggestion is a no-op."""
        page = _make_page()
        _setup_helper_ui(page)

        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=1,
            end_line=1,
            original_content="line1",
            suggested_content="new",
            status="rejected",
        )

        mock_card = MagicMock()
        mock_btn_row = MagicMock()

        page._reject_suggestion(suggestion, mock_card, mock_btn_row)

        # Should not modify card classes since status is already rejected
        mock_card.classes.assert_not_called()

    @patch("tj_chat.pages.editor.ui")
    def test_reject_does_not_modify_editor(self, mock_ui) -> None:
        """Verify rejecting a suggestion does not change editor content."""
        page = _make_page()
        _setup_helper_ui(page)
        original_content = page._editor.value

        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=1,
            end_line=1,
            original_content="line1",
            suggested_content="new",
            status="pending",
        )

        mock_card = MagicMock()
        mock_btn_row = MagicMock()
        mock_ui.label = MagicMock(return_value=MagicMock(classes=MagicMock()))

        page._reject_suggestion(suggestion, mock_card, mock_btn_row)

        assert page._editor.value == original_content


class TestConversationHistory:
    """Tests for conversation history management."""

    @patch("tj_chat.pages.editor.ui")
    def test_user_message_added_to_conversation(self, mock_ui) -> None:
        """Verify user messages are added to conversation history."""
        page = _make_page()
        _setup_helper_ui(page)

        mock_ui.row.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.row.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.chat_message = MagicMock()

        page._display_helper_user_message("Hello")

        assert len(page._conversation) == 1
        assert page._conversation[0] == {"role": "user", "content": "Hello"}

    @patch("tj_chat.pages.editor.ui")
    def test_assistant_message_added_to_conversation(self, mock_ui) -> None:
        """Verify assistant messages are added to conversation history."""
        page = _make_page()
        _setup_helper_ui(page)

        mock_ui.row.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.row.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.chat_message = MagicMock()

        page._display_helper_assistant_message("Use task keyword")

        assert len(page._conversation) == 1
        assert page._conversation[0] == {
            "role": "assistant",
            "content": "Use task keyword",
        }

    @patch("tj_chat.pages.editor.ui")
    def test_error_message_added_to_conversation(self, mock_ui) -> None:
        """Verify error messages are added to conversation history."""
        page = _make_page()
        _setup_helper_ui(page)

        mock_ui.card.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.card.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.row.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_ui.row.return_value.__exit__ = MagicMock(return_value=False)
        mock_ui.icon = MagicMock(return_value=MagicMock(classes=MagicMock()))
        mock_ui.label = MagicMock(return_value=MagicMock(classes=MagicMock()))
        mock_ui.button = MagicMock(return_value=MagicMock(props=MagicMock()))

        page._display_helper_error("Service unavailable")

        assert len(page._conversation) == 1
        assert page._conversation[0] == {
            "role": "error",
            "content": "Service unavailable",
        }
