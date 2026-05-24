"""Unit tests for the NiceGUI application entry point."""

from __future__ import annotations

from unittest.mock import patch

import pytest


def test_create_app_is_importable() -> None:
    """Verify create_app can be imported from tj_chat.app."""
    from tj_chat.app import create_app

    assert callable(create_app)


def test_main_is_importable() -> None:
    """Verify main can be imported from tj_chat.app."""
    from tj_chat.app import main

    assert callable(main)


def test_nav_header_is_importable() -> None:
    """Verify _nav_header helper can be imported."""
    from tj_chat.app import _nav_header

    assert callable(_nav_header)


def test_create_app_registers_pages() -> None:
    """Verify create_app registers the expected page routes without errors."""
    from tj_chat.app import create_app

    with patch("tj_chat.app.app.add_static_files") as mock_static:
        create_app()
        # Static files should be configured for reports
        mock_static.assert_called_once()
        call_args = mock_static.call_args
        assert call_args[0][0] == "/report-files"
