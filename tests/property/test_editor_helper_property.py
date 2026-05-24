"""Property-based tests for HelperService.

# Feature: project-file-editor, Property 8: Whitespace input rejection
# Feature: project-file-editor, Property 9: Helper context assembly

**Validates: Requirements 5.4, 5.5, 5.9, 7.1, 7.2**

Property 8: Whitespace input rejection
- For any string composed entirely of whitespace characters (spaces, tabs,
  newlines) or the empty string, the helper panel submission handler SHALL
  reject the input without sending a request to the ChatService.

Property 9: Helper context assembly
- For any user message submitted in the helper panel with a file loaded in
  the editor, the context payload sent to the ChatService SHALL include:
  the current file name, the current file content, the cursor line number,
  the 10 lines above and below the cursor (or fewer at file boundaries),
  and relevant TJ documentation search results for the user's query.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.editor_models import EditorContext
from tj_chat.helper_service import HelperService
from tj_chat.models import DocSection
from tj_chat.settings import ChatSettings


# --- Strategies ---

# Strategy for whitespace-only strings (Property 8)
_whitespace_only = st.text(
    alphabet=st.sampled_from(" \t\n\r\x0b\x0c"),
    min_size=0,
    max_size=50,
)

# Strategy for non-empty user messages (Property 9)
_user_message = st.text(min_size=1, max_size=100).filter(lambda s: s.strip() != "")

# Strategy for file paths (non-empty, no null bytes)
_file_path = st.text(
    alphabet=st.characters(exclude_characters="\x00"),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip() != "")

# Strategy for file content (multi-line text)
_file_content = st.text(
    alphabet=st.characters(exclude_characters="\x00", exclude_categories=("Cs",)),
    min_size=1,
    max_size=500,
)

# Strategy for cursor line (positive integer)
_cursor_line = st.integers(min_value=1, max_value=200)

# Strategy for surrounding lines text
_surrounding_lines = st.text(
    alphabet=st.characters(exclude_characters="\x00", exclude_categories=("Cs",)),
    min_size=1,
    max_size=200,
)

# Strategy for project file lists
_project_files = st.lists(
    st.text(
        alphabet=st.characters(exclude_characters="\x00", exclude_categories=("Cs",)),
        min_size=1,
        max_size=30,
    ).filter(lambda s: s.strip() != ""),
    min_size=0,
    max_size=5,
)


def _make_settings() -> ChatSettings:
    """Create minimal ChatSettings for testing."""
    return ChatSettings(
        lm_studio_url="http://localhost:1234/v1",
        model_name="test-model",
    )


class TestWhitespaceInputRejection:
    """Property 8: Whitespace input rejection.

    # Feature: project-file-editor, Property 8: Whitespace input rejection

    **Validates: Requirements 5.4**

    For any string of only whitespace/empty, submission is rejected without
    ChatService call.
    """

    @given(whitespace_input=_whitespace_only)
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_whitespace_only_input_rejected_without_llm_call(
        self, whitespace_input: str
    ) -> None:
        """Whitespace-only or empty input is rejected without calling the LLM."""
        mock_settings = _make_settings()
        mock_tj_docs = MagicMock()

        service = HelperService(settings=mock_settings, tj_docs=mock_tj_docs)

        # Patch the OpenAI client to detect if it's called
        with patch.object(
            service._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            context = EditorContext(
                file_path="test.tjp",
                file_content="task t1 {}",
                cursor_line=1,
            )

            result = await service.send_message(whitespace_input, context)

            # The LLM should NOT have been called
            mock_create.assert_not_called()

            # The result should indicate rejection (empty text or error)
            assert result.text == "" or result.error is not None


class TestHelperContextAssembly:
    """Property 9: Helper context assembly.

    # Feature: project-file-editor, Property 9: Helper context assembly

    **Validates: Requirements 5.5, 5.9, 7.1, 7.2**

    For any message with a file loaded: context includes file name, content,
    cursor line, surrounding lines, and TJ doc results.
    """

    @given(
        user_message=_user_message,
        file_path=_file_path,
        file_content=_file_content,
        cursor_line=_cursor_line,
        surrounding_lines=_surrounding_lines,
        project_files=_project_files,
    )
    @settings(max_examples=100, deadline=None)
    @pytest.mark.asyncio
    async def test_context_includes_file_name_content_cursor_and_docs(
        self,
        user_message: str,
        file_path: str,
        file_content: str,
        cursor_line: int,
        surrounding_lines: str,
        project_files: list[str],
    ) -> None:
        """The user message sent to the LLM contains file name, content, cursor line, surrounding lines, and TJ doc results."""
        mock_settings = _make_settings()

        # Create mock TJ documentation service that returns results
        doc_title = "task"
        doc_content = "The task keyword defines a new task."
        mock_tj_docs = MagicMock()
        mock_tj_docs.search.return_value = [
            DocSection(
                title=doc_title,
                content=doc_content,
                relevance_score=0.9,
            )
        ]

        service = HelperService(settings=mock_settings, tj_docs=mock_tj_docs)

        # Capture the messages sent to the LLM
        captured_messages: list[dict] = []

        async def capture_create(**kwargs):  # type: ignore[no-untyped-def]
            captured_messages.extend(kwargs.get("messages", []))
            # Return a mock response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Here is some help."
            return mock_response

        with patch.object(
            service._client.chat.completions,
            "create",
            side_effect=capture_create,
        ):
            context = EditorContext(
                file_path=file_path,
                file_content=file_content,
                cursor_line=cursor_line,
                surrounding_lines=surrounding_lines,
                project_files=project_files,
            )

            await service.send_message(user_message, context)

        # Verify the LLM was called
        assert len(captured_messages) > 0, "No messages were sent to the LLM"

        # Find the user message in the captured messages
        user_messages = [m for m in captured_messages if m.get("role") == "user"]
        assert len(user_messages) > 0, "No user message found in LLM call"

        # The last user message should contain all context elements
        last_user_msg = user_messages[-1]["content"]

        # Requirement 7.1: file name included in context
        assert file_path in last_user_msg, (
            f"File path '{file_path}' not found in context sent to LLM"
        )

        # Requirement 7.1: file content included in context
        assert file_content in last_user_msg, (
            "File content not found in context sent to LLM"
        )

        # Requirement 7.2: cursor line number included in context
        assert str(cursor_line) in last_user_msg, (
            f"Cursor line {cursor_line} not found in context sent to LLM"
        )

        # Requirement 7.2: surrounding lines included in context
        assert surrounding_lines in last_user_msg, (
            "Surrounding lines not found in context sent to LLM"
        )

        # Requirement 5.9: TJ documentation search results included
        assert doc_title in last_user_msg, (
            f"TJ doc title '{doc_title}' not found in context sent to LLM"
        )
        assert doc_content in last_user_msg, (
            f"TJ doc content not found in context sent to LLM"
        )

        # Verify TJ docs search was called with the user's message
        mock_tj_docs.search.assert_called_once_with(user_message)
