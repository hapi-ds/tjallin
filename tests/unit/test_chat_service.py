"""Unit tests for the chat service module."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tj_chat.chat_service import ChatService, _build_tool_definitions, _default_confirm
from tj_chat.models import (
    AgentResponse,
    FunctionCall,
    Message,
    ProjectSummary,
    ToolCallMessage,
    ToolResult,
)
from tj_chat.settings import ChatSettings


@pytest.fixture
def settings() -> ChatSettings:
    """Create test settings."""
    return ChatSettings(
        lm_studio_url="http://localhost:1234/v1",
        model_name=None,
        token_limit=4096,
        connection_timeout=10,
        response_timeout=120,
    )


@pytest.fixture
def settings_with_model() -> ChatSettings:
    """Create test settings with a configured model name."""
    return ChatSettings(
        lm_studio_url="http://localhost:1234/v1",
        model_name="my-custom-model",
        token_limit=4096,
        connection_timeout=10,
        response_timeout=120,
    )


@pytest.fixture
def mock_tool_executor() -> MagicMock:
    """Create a mock tool executor."""
    executor = MagicMock()
    executor.execute = AsyncMock(
        return_value=ToolResult(
            tool_call_id="tc_1",
            success=True,
            content="Tool executed successfully.",
        )
    )
    return executor


@pytest.fixture
def service(settings: ChatSettings, mock_tool_executor: MagicMock) -> ChatService:
    """Create a ChatService instance with mocked dependencies."""
    return ChatService(settings=settings, tool_executor=mock_tool_executor)


@pytest.fixture
def service_with_model(
    settings_with_model: ChatSettings, mock_tool_executor: MagicMock
) -> ChatService:
    """Create a ChatService with a configured model name."""
    return ChatService(settings=settings_with_model, tool_executor=mock_tool_executor)


class TestConnect:
    """Tests for ChatService.connect()."""

    def test_connect_success_uses_first_model(self, service: ChatService) -> None:
        """When no model is configured, connect uses the first available model."""
        mock_model = MagicMock()
        mock_model.id = "test-model-7b"

        with patch.object(service._client.models, "list", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = iter([mock_model])
            result = asyncio.run(service.connect())

        assert result.success is True
        assert result.model_name == "test-model-7b"
        assert result.error is None

    def test_connect_success_uses_configured_model(
        self, service_with_model: ChatService
    ) -> None:
        """When a model is configured, connect uses it directly."""
        mock_model = MagicMock()
        mock_model.id = "other-model"

        with patch.object(
            service_with_model._client.models, "list", new_callable=AsyncMock
        ) as mock_list:
            mock_list.return_value = iter([mock_model])
            result = asyncio.run(service_with_model.connect())

        assert result.success is True
        assert result.model_name == "my-custom-model"

    def test_connect_no_models_available(self, service: ChatService) -> None:
        """When no models are available, connect returns an error."""
        with patch.object(service._client.models, "list", new_callable=AsyncMock) as mock_list:
            mock_list.return_value = iter([])
            result = asyncio.run(service.connect())

        assert result.success is False
        assert result.error is not None
        assert "No models available" in result.error

    def test_connect_timeout_error(self, service: ChatService) -> None:
        """When LM Studio is unreachable, connect returns a connection error."""
        with patch.object(service._client.models, "list", new_callable=AsyncMock) as mock_list:
            mock_list.side_effect = TimeoutError("Connection timed out")
            result = asyncio.run(service.connect())

        assert result.success is False
        assert result.error is not None
        assert "localhost:1234" in result.error

    def test_connect_connection_refused(self, service: ChatService) -> None:
        """When connection is refused, connect returns an error with endpoint URL."""
        with patch.object(service._client.models, "list", new_callable=AsyncMock) as mock_list:
            mock_list.side_effect = ConnectionError("Connection refused")
            result = asyncio.run(service.connect())

        assert result.success is False
        assert result.error is not None
        assert "http://localhost:1234/v1" in result.error


class TestSendMessage:
    """Tests for ChatService.send_message()."""

    def test_simple_text_response(self, service: ChatService) -> None:
        """A simple response without tool calls returns text directly."""
        mock_choice = MagicMock()
        mock_choice.message.tool_calls = None
        mock_choice.message.content = "Hello! How can I help?"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(
            service._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = asyncio.run(service.send_message("Hi there"))

        assert isinstance(result, AgentResponse)
        assert result.text == "Hello! How can I help?"
        assert result.tool_actions == []

    def test_tool_call_loop(
        self, service: ChatService, mock_tool_executor: MagicMock
    ) -> None:
        """When the LLM returns tool calls, they are executed and fed back."""
        # First response: tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_123"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "list_tasks"
        mock_tool_call.function.arguments = "{}"

        mock_choice_1 = MagicMock()
        mock_choice_1.message.tool_calls = [mock_tool_call]
        mock_choice_1.message.content = None

        mock_response_1 = MagicMock()
        mock_response_1.choices = [mock_choice_1]

        # Second response: final text
        mock_choice_2 = MagicMock()
        mock_choice_2.message.tool_calls = None
        mock_choice_2.message.content = "Here are your tasks."

        mock_response_2 = MagicMock()
        mock_response_2.choices = [mock_choice_2]

        with patch.object(
            service._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = [mock_response_1, mock_response_2]
            result = asyncio.run(service.send_message("Show me my tasks"))

        assert result.text == "Here are your tasks."
        assert len(result.tool_actions) == 1
        assert result.tool_actions[0].tool_name == "list_tasks"
        mock_tool_executor.execute.assert_called_once()

    def test_multiple_tool_calls_in_one_response(
        self, service: ChatService, mock_tool_executor: MagicMock
    ) -> None:
        """Multiple tool calls in a single response are all executed."""
        mock_tc_1 = MagicMock()
        mock_tc_1.id = "call_1"
        mock_tc_1.type = "function"
        mock_tc_1.function.name = "list_tasks"
        mock_tc_1.function.arguments = "{}"

        mock_tc_2 = MagicMock()
        mock_tc_2.id = "call_2"
        mock_tc_2.type = "function"
        mock_tc_2.function.name = "list_resources"
        mock_tc_2.function.arguments = "{}"

        mock_choice_1 = MagicMock()
        mock_choice_1.message.tool_calls = [mock_tc_1, mock_tc_2]
        mock_choice_1.message.content = None

        mock_response_1 = MagicMock()
        mock_response_1.choices = [mock_choice_1]

        mock_choice_2 = MagicMock()
        mock_choice_2.message.tool_calls = None
        mock_choice_2.message.content = "Done."

        mock_response_2 = MagicMock()
        mock_response_2.choices = [mock_choice_2]

        with patch.object(
            service._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = [mock_response_1, mock_response_2]
            result = asyncio.run(service.send_message("Show everything"))

        assert len(result.tool_actions) == 2
        assert mock_tool_executor.execute.call_count == 2

    def test_api_error_returns_error_response(self, service: ChatService) -> None:
        """When the API call fails, an error response is returned."""
        with patch.object(
            service._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = Exception("API error")
            result = asyncio.run(service.send_message("Hello"))

        assert "Error communicating with LM Studio" in result.text

    def test_max_iterations_safety(
        self, service: ChatService, mock_tool_executor: MagicMock
    ) -> None:
        """The tool call loop stops after max iterations to prevent infinite loops."""
        # Always return a tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_loop"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "list_tasks"
        mock_tool_call.function.arguments = "{}"

        mock_choice = MagicMock()
        mock_choice.message.tool_calls = [mock_tool_call]
        mock_choice.message.content = None

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch.object(
            service._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.return_value = mock_response
            result = asyncio.run(service.send_message("Loop forever"))

        assert "maximum number of tool call iterations" in result.text

    def test_malformed_tool_arguments(
        self, service: ChatService, mock_tool_executor: MagicMock
    ) -> None:
        """Malformed JSON in tool arguments defaults to empty dict."""
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_bad"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "list_tasks"
        mock_tool_call.function.arguments = "not valid json{{"

        mock_choice_1 = MagicMock()
        mock_choice_1.message.tool_calls = [mock_tool_call]
        mock_choice_1.message.content = None

        mock_response_1 = MagicMock()
        mock_response_1.choices = [mock_choice_1]

        mock_choice_2 = MagicMock()
        mock_choice_2.message.tool_calls = None
        mock_choice_2.message.content = "Done."

        mock_response_2 = MagicMock()
        mock_response_2.choices = [mock_choice_2]

        with patch.object(
            service._client.chat.completions, "create", new_callable=AsyncMock
        ) as mock_create:
            mock_create.side_effect = [mock_response_1, mock_response_2]
            result = asyncio.run(service.send_message("Do something"))

        # Should still work — arguments default to {}
        assert result.text == "Done."
        mock_tool_executor.execute.assert_called_once()


class TestResetSession:
    """Tests for ChatService.reset_session()."""

    def test_reset_clears_conversation(self, service: ChatService) -> None:
        """After reset, conversation history is empty."""
        service._conversation.add_message(Message(role="user", content="Old message"))
        asyncio.run(service.reset_session())
        messages = service._conversation.get_messages("sys")
        assert len(messages) == 1  # Only system prompt


class TestSetSystemPrompt:
    """Tests for ChatService.set_system_prompt()."""

    def test_sets_system_prompt_from_project_summary(self, service: ChatService) -> None:
        """set_system_prompt builds and caches the prompt."""
        summary = ProjectSummary(
            project_name="Test Project",
            start_date="2024-01-01",
            end_date="2024-12-31",
            now_date="2024-06-15",
            file_tree=["project.tjp", "tasks.tji"],
            resource_ids=["dev1", "dev2"],
            top_level_tasks=["development", "testing"],
        )
        service.set_system_prompt(summary)
        assert "Test Project" in service._system_prompt
        assert "project.tjp" in service._system_prompt


class TestMessageToDict:
    """Tests for ChatService._message_to_dict()."""

    def test_simple_user_message(self) -> None:
        msg = Message(role="user", content="Hello")
        result = ChatService._message_to_dict(msg)
        assert result == {"role": "user", "content": "Hello"}

    def test_tool_message_includes_tool_call_id(self) -> None:
        msg = Message(role="tool", content="result", tool_call_id="tc_1", name="read_file")
        result = ChatService._message_to_dict(msg)
        assert result["role"] == "tool"
        assert result["content"] == "result"
        assert result["tool_call_id"] == "tc_1"
        assert result["name"] == "read_file"

    def test_assistant_message_with_tool_calls(self) -> None:
        msg = Message(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCallMessage(
                    id="call_1",
                    type="function",
                    function=FunctionCall(name="list_tasks", arguments="{}"),
                )
            ],
        )
        result = ChatService._message_to_dict(msg)
        assert result["role"] == "assistant"
        assert "content" not in result  # None content is excluded
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["id"] == "call_1"
        assert result["tool_calls"][0]["function"]["name"] == "list_tasks"

    def test_none_content_excluded(self) -> None:
        msg = Message(role="assistant", content=None)
        result = ChatService._message_to_dict(msg)
        assert "content" not in result


class TestBuildToolDefinitions:
    """Tests for _build_tool_definitions()."""

    def test_returns_list_of_dicts(self) -> None:
        tools = _build_tool_definitions()
        assert isinstance(tools, list)
        assert len(tools) > 0
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "parameters" in tool["function"]

    def test_all_expected_tools_present(self) -> None:
        tools = _build_tool_definitions()
        tool_names = {t["function"]["name"] for t in tools}
        expected = {
            "read_file",
            "list_files",
            "list_tasks",
            "list_resources",
            "find_task",
            "find_resource",
            "write_file",
            "update_task",
            "add_task",
            "update_resource",
            "write_timesheet",
            "write_journal",
            "write_report",
            "compile_project",
            "search_tj_docs",
        }
        assert expected == tool_names

    def test_tool_parameters_have_type_object(self) -> None:
        tools = _build_tool_definitions()
        for tool in tools:
            params = tool["function"]["parameters"]
            assert params["type"] == "object"
            assert "properties" in params


class TestDefaultConfirm:
    """Tests for _default_confirm()."""

    def test_always_returns_true(self) -> None:
        assert asyncio.run(_default_confirm("any summary")) is True


class TestConfirmFnProperty:
    """Tests for the confirm_fn property."""

    def test_default_confirm_fn(self, service: ChatService) -> None:
        assert service.confirm_fn is not None

    def test_custom_confirm_fn(self, service: ChatService) -> None:
        custom_fn = AsyncMock(return_value=False)
        service.confirm_fn = custom_fn
        assert service.confirm_fn is custom_fn
