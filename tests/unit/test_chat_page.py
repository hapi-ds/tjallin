"""Unit tests for the ChatPageUI class."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tj_chat.models import ConnectionResult


def test_chat_page_ui_is_importable() -> None:
    """Verify ChatPageUI can be imported."""
    from tj_chat.pages.chat import ChatPageUI

    assert callable(ChatPageUI)


def test_chat_page_ui_init_stores_services() -> None:
    """Verify ChatPageUI stores chat_service and tj_docs references."""
    from tj_chat.pages.chat import ChatPageUI

    mock_service = MagicMock()
    mock_docs = MagicMock()
    mock_docs.is_available = True

    page = ChatPageUI(chat_service=mock_service, tj_docs=mock_docs)

    assert page._chat_service is mock_service
    assert page._tj_docs is mock_docs
    assert page._processing is False


def test_chat_page_ui_init_without_tj_docs() -> None:
    """Verify ChatPageUI works without TJ docs (None)."""
    from tj_chat.pages.chat import ChatPageUI

    mock_service = MagicMock()

    page = ChatPageUI(chat_service=mock_service, tj_docs=None)

    assert page._tj_docs is None
    assert page._pending_confirmation is None


def test_chat_page_ui_init_connected_false_by_default() -> None:
    """Verify ChatPageUI starts in disconnected state."""
    from tj_chat.pages.chat import ChatPageUI

    mock_service = MagicMock()
    page = ChatPageUI(chat_service=mock_service)

    assert page._connected is False


def test_check_connection_success_sets_connected() -> None:
    """Verify successful connection sets _connected to True."""
    from tj_chat.pages.chat import ChatPageUI

    mock_service = MagicMock()
    mock_service.connect = AsyncMock(
        return_value=ConnectionResult(success=True, model_name="test-model")
    )
    mock_service._settings = MagicMock()
    mock_service._settings.lm_studio_url = "http://localhost:1234/v1"

    page = ChatPageUI(chat_service=mock_service)
    # Mock UI elements that _check_connection interacts with
    page._connection_banner = MagicMock()
    page._connection_error_label = MagicMock()
    page._connection_endpoint_label = MagicMock()
    page._input = MagicMock()
    page._send_button = MagicMock()

    asyncio.run(page._check_connection())

    assert page._connected is True
    page._connection_banner.classes.assert_called_with(add="hidden")
    page._input.props.assert_called_with(remove="disable")
    page._send_button.props.assert_called_with(remove="disable")


def test_check_connection_failure_shows_banner() -> None:
    """Verify failed connection shows error banner with endpoint URL."""
    from tj_chat.pages.chat import ChatPageUI

    mock_service = MagicMock()
    mock_service.connect = AsyncMock(
        return_value=ConnectionResult(
            success=False,
            error="Connection refused",
        )
    )
    mock_service._settings = MagicMock()
    mock_service._settings.lm_studio_url = "http://myhost:5555/v1"

    page = ChatPageUI(chat_service=mock_service)
    page._connection_banner = MagicMock()
    page._connection_error_label = MagicMock()
    page._connection_endpoint_label = MagicMock()
    page._input = MagicMock()
    page._send_button = MagicMock()

    asyncio.run(page._check_connection())

    assert page._connected is False
    page._connection_banner.classes.assert_called_with(remove="hidden")
    page._input.props.assert_called_with(add="disable")
    page._send_button.props.assert_called_with(add="disable")
    assert page._connection_error_label.text == "Connection refused"
    assert page._connection_endpoint_label.text == "Endpoint: http://myhost:5555/v1"


def test_on_send_blocked_when_disconnected() -> None:
    """Verify _on_send does nothing when not connected."""
    from tj_chat.pages.chat import ChatPageUI

    mock_service = MagicMock()
    mock_service.send_message = AsyncMock()

    page = ChatPageUI(chat_service=mock_service)
    page._connected = False
    page._input = MagicMock()
    page._input.value = "hello"

    asyncio.run(page._on_send())

    # send_message should not have been called
    mock_service.send_message.assert_not_called()


def test_retry_connection_calls_check_connection() -> None:
    """Verify retry button triggers a new connection check."""
    from tj_chat.pages.chat import ChatPageUI

    mock_service = MagicMock()
    mock_service.connect = AsyncMock(
        return_value=ConnectionResult(success=True, model_name="test-model")
    )
    mock_service._settings = MagicMock()
    mock_service._settings.lm_studio_url = "http://localhost:1234/v1"

    page = ChatPageUI(chat_service=mock_service)
    page._connection_banner = MagicMock()
    page._connection_error_label = MagicMock()
    page._connection_endpoint_label = MagicMock()
    page._input = MagicMock()
    page._send_button = MagicMock()

    asyncio.run(page._retry_connection())

    mock_service.connect.assert_called_once()
    assert page._connected is True


def test_chat_page_ui_app_integration() -> None:
    """Verify the chat page route in app.py uses ChatPageUI."""
    from tj_chat.app import create_app

    with patch("tj_chat.app.app.add_static_files"):
        # Should not raise
        create_app()
