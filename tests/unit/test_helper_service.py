"""Unit tests for the HelperService.

Tests context assembly, response parsing, session management,
timeout handling, and whitespace input rejection.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from tj_chat.editor_models import DiffSuggestion, EditorContext, HelperResponse
from tj_chat.helper_service import HelperService, parse_diff_suggestions
from tj_chat.settings import ChatSettings


@pytest.fixture
def settings() -> ChatSettings:
    """Create test settings."""
    return ChatSettings(
        lm_studio_url="http://localhost:1234/v1",
        model_name="test-model",
        project_path=Path("/test/project"),
    )


@pytest.fixture
def mock_tj_docs() -> MagicMock:
    """Create a mock TJDocumentationService."""
    from tj_chat.models import DocSection

    mock = MagicMock()
    mock.search.return_value = [
        DocSection(
            title="task",
            content="The task keyword defines a new task.",
            relevance_score=0.9,
        )
    ]
    return mock


@pytest.fixture
def editor_context() -> EditorContext:
    """Create a sample editor context."""
    return EditorContext(
        file_path="project.tjp",
        file_content="project acme \"Acme\" {\n  start 2024-01-01\n  end 2024-12-31\n}\n\ntask dev \"Development\" {\n  effort 20d\n  allocate dev1\n}\n",
        cursor_line=6,
        surrounding_lines="project acme \"Acme\" {\n  start 2024-01-01\n  end 2024-12-31\n}\n\ntask dev \"Development\" {\n  effort 20d\n  allocate dev1\n}\n",
        project_files=["project.tjp", "resources.tji", "reports.tji"],
    )


@pytest.fixture
def helper_service(settings: ChatSettings, mock_tj_docs: MagicMock) -> HelperService:
    """Create a HelperService with mocked dependencies."""
    return HelperService(settings=settings, tj_docs=mock_tj_docs)


class TestWhitespaceRejection:
    """Test that empty/whitespace-only input is rejected."""

    @pytest.mark.asyncio
    async def test_empty_string_rejected(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Empty string should be rejected without calling LLM."""
        result = await helper_service.send_message("", editor_context)
        assert result.error is not None
        assert result.text == ""

    @pytest.mark.asyncio
    async def test_whitespace_only_rejected(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Whitespace-only string should be rejected without calling LLM."""
        result = await helper_service.send_message("   \t\n  ", editor_context)
        assert result.error is not None
        assert result.text == ""

    @pytest.mark.asyncio
    async def test_valid_message_not_rejected(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Non-empty message should not be rejected (will attempt LLM call)."""
        # Mock the OpenAI client to return a response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Here is some help."

        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await helper_service.send_message("How do I define a task?", editor_context)
            assert result.error is None
            assert result.text == "Here is some help."


class TestContextAssembly:
    """Test that context is properly assembled for the LLM."""

    @pytest.mark.asyncio
    async def test_context_includes_file_path(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Context should include the current file path."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await helper_service.send_message("help", editor_context)

            # Check the messages sent to the LLM
            call_kwargs = mock_create.call_args[1]
            messages = call_kwargs["messages"]
            user_msg = messages[-1]["content"]
            assert "project.tjp" in user_msg

    @pytest.mark.asyncio
    async def test_context_includes_cursor_line(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Context should include the cursor line number."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await helper_service.send_message("help", editor_context)

            call_kwargs = mock_create.call_args[1]
            messages = call_kwargs["messages"]
            user_msg = messages[-1]["content"]
            assert "6" in user_msg

    @pytest.mark.asyncio
    async def test_context_includes_project_files(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Context should include the project file list."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await helper_service.send_message("help", editor_context)

            call_kwargs = mock_create.call_args[1]
            messages = call_kwargs["messages"]
            user_msg = messages[-1]["content"]
            assert "resources.tji" in user_msg
            assert "reports.tji" in user_msg

    @pytest.mark.asyncio
    async def test_context_includes_tj_docs(
        self,
        helper_service: HelperService,
        editor_context: EditorContext,
        mock_tj_docs: MagicMock,
    ) -> None:
        """Context should include TJ documentation search results."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await helper_service.send_message("How do I define a task?", editor_context)

            # Verify tj_docs.search was called with the user message
            mock_tj_docs.search.assert_called_once_with("How do I define a task?")

            # Verify doc content is in the message
            call_kwargs = mock_create.call_args[1]
            messages = call_kwargs["messages"]
            user_msg = messages[-1]["content"]
            assert "task" in user_msg
            assert "The task keyword defines a new task." in user_msg

    @pytest.mark.asyncio
    async def test_context_without_tj_docs(
        self, settings: ChatSettings, editor_context: EditorContext
    ) -> None:
        """Service should work without TJ docs (None)."""
        service = HelperService(settings=settings, tj_docs=None)

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch.object(
            service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await service.send_message("help", editor_context)
            assert result.error is None
            assert result.text == "Response"

    @pytest.mark.asyncio
    async def test_system_prompt_included(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """System prompt should be included in messages."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await helper_service.send_message("help", editor_context)

            call_kwargs = mock_create.call_args[1]
            messages = call_kwargs["messages"]
            assert messages[0]["role"] == "system"
            assert "TaskJuggler" in messages[0]["content"]


class TestConversationHistory:
    """Test conversation history management."""

    @pytest.mark.asyncio
    async def test_history_maintained(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Conversation history should be maintained across messages."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "First response"

        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await helper_service.send_message("first question", editor_context)

        assert len(helper_service.history) == 2  # user + assistant

        mock_response.choices[0].message.content = "Second response"

        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ) as mock_create:
            await helper_service.send_message("second question", editor_context)

            # Should include previous messages in the call
            call_kwargs = mock_create.call_args[1]
            messages = call_kwargs["messages"]
            # system + first user + first assistant + second user = 4
            assert len(messages) == 4

        assert len(helper_service.history) == 4  # 2 user + 2 assistant

    @pytest.mark.asyncio
    async def test_reset_session_clears_history(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """reset_session should clear all conversation history."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"

        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            await helper_service.send_message("question", editor_context)

        assert len(helper_service.history) > 0

        helper_service.reset_session()
        assert len(helper_service.history) == 0


class TestErrorHandling:
    """Test timeout and connection error handling."""

    @pytest.mark.asyncio
    async def test_timeout_error(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Timeout should return error response."""
        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("Request timed out"),
        ):
            result = await helper_service.send_message("help", editor_context)
            assert result.error is not None
            assert "timed out" in result.error.lower()
            assert result.text == ""

    @pytest.mark.asyncio
    async def test_timeout_does_not_add_to_history(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Failed requests should not be added to conversation history."""
        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=httpx.TimeoutException("Request timed out"),
        ):
            await helper_service.send_message("help", editor_context)
            assert len(helper_service.history) == 0

    @pytest.mark.asyncio
    async def test_connection_error(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Connection error should return error response."""
        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = await helper_service.send_message("help", editor_context)
            assert result.error is not None
            assert "unavailable" in result.error.lower()
            assert result.text == ""

    @pytest.mark.asyncio
    async def test_network_error(
        self, helper_service: HelperService, editor_context: EditorContext
    ) -> None:
        """Network error should return error response."""
        with patch.object(
            helper_service._client.chat.completions,
            "create",
            new_callable=AsyncMock,
            side_effect=httpx.NetworkError("Network unreachable"),
        ):
            result = await helper_service.send_message("help", editor_context)
            assert result.error is not None
            assert "unavailable" in result.error.lower()


class TestDiffSuggestionParsing:
    """Test parsing of annotated code blocks from LLM responses."""

    def test_parse_single_suggestion(self) -> None:
        """Single annotated code block should produce one DiffSuggestion."""
        response = (
            "Here's a fix:\n\n"
            "```tj path=project.tjp lines=6-8\n"
            "task dev \"Development\" {\n"
            "  effort 30d\n"
            "  allocate dev1, dev2\n"
            "}\n"
            "```\n"
        )
        context = EditorContext(
            file_path="project.tjp",
            file_content="line1\nline2\nline3\nline4\nline5\ntask dev \"Development\" {\n  effort 20d\n  allocate dev1\n}\n",
            cursor_line=6,
        )

        suggestions = parse_diff_suggestions(response, context)
        assert len(suggestions) == 1
        assert suggestions[0].file_path == "project.tjp"
        assert suggestions[0].start_line == 6
        assert suggestions[0].end_line == 8
        assert "effort 30d" in suggestions[0].suggested_content

    def test_parse_multiple_suggestions(self) -> None:
        """Multiple annotated code blocks should produce multiple DiffSuggestions."""
        response = (
            "Here are two changes:\n\n"
            "```tj path=project.tjp lines=1-2\n"
            "project acme \"Acme Project\" {\n"
            "  start 2024-01-01\n"
            "```\n\n"
            "And also:\n\n"
            "```tj path=resources.tji lines=1-1\n"
            "resource dev1 \"Developer 1\"\n"
            "```\n"
        )
        context = EditorContext(
            file_path="project.tjp",
            file_content="project acme \"Acme\" {\n  start 2024-01-01\n",
        )

        suggestions = parse_diff_suggestions(response, context)
        assert len(suggestions) == 2
        assert suggestions[0].file_path == "project.tjp"
        assert suggestions[1].file_path == "resources.tji"

    def test_parse_no_suggestions(self) -> None:
        """Response without annotated blocks should produce empty list."""
        response = "Here's some general advice about TaskJuggler syntax."
        context = EditorContext(file_path="project.tjp")

        suggestions = parse_diff_suggestions(response, context)
        assert suggestions == []

    def test_parse_extracts_original_content(self) -> None:
        """Parser should extract original content from context for matching file."""
        response = (
            "```tj path=project.tjp lines=2-3\n"
            "  start 2024-06-01\n"
            "  end 2025-12-31\n"
            "```\n"
        )
        context = EditorContext(
            file_path="project.tjp",
            file_content="project acme \"Acme\" {\n  start 2024-01-01\n  end 2024-12-31\n}\n",
        )

        suggestions = parse_diff_suggestions(response, context)
        assert len(suggestions) == 1
        assert suggestions[0].original_content == "  start 2024-01-01\n  end 2024-12-31"

    def test_parse_different_file_no_original(self) -> None:
        """Suggestions for a different file should have empty original_content."""
        response = (
            "```tj path=other.tji lines=1-1\n"
            "resource dev2 \"Developer 2\"\n"
            "```\n"
        )
        context = EditorContext(
            file_path="project.tjp",
            file_content="project acme \"Acme\" {\n}\n",
        )

        suggestions = parse_diff_suggestions(response, context)
        assert len(suggestions) == 1
        assert suggestions[0].original_content == ""
