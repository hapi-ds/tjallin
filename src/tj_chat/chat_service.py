"""Chat service orchestrating LM Studio communication and conversation flow.

Manages the connection to LM Studio, sends messages through the OpenAI-compatible
API, handles tool call loops, and returns structured agent responses.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from tj_chat.conversation import ConversationManager
from tj_chat.models import (
    AgentResponse,
    ConnectionResult,
    FunctionCall,
    Message,
    ToolAction,
    ToolCall,
    ToolCallMessage,
)
from tj_chat.settings import ChatSettings
from tj_chat.system_prompt import build_system_prompt

if TYPE_CHECKING:
    from tj_chat.models import ProjectSummary
    from tj_chat.tj_docs import TJDocumentationService
    from tj_chat.tool_executor import ToolExecutor

logger = logging.getLogger(__name__)

# Type alias for the confirmation callback used by tool executor
ConfirmFn = Callable[[str], Awaitable[bool]]

# Maximum number of tool call iterations to prevent infinite loops
_MAX_TOOL_ITERATIONS = 10


def _build_tool_definitions() -> list[dict]:
    """Build OpenAI function-calling tool definitions for all available tools.

    Returns:
        List of tool definition dicts in OpenAI function-calling format.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read the contents of a project file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": (
                                "Relative path to the file within the project."
                            ),
                        }
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_files",
                "description": "List files in the project directory or subdirectory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "subdirectory": {
                            "type": "string",
                            "description": (
                                "Subdirectory to list (relative to project root)."
                            ),
                        }
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_tasks",
                "description": "List all tasks with hierarchy, effort, and allocations.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_resources",
                "description": "List all resources defined in the project.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_task",
                "description": "Find tasks matching a query by name or ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query to match against task names and IDs.",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_resource",
                "description": "Find resources matching a query by name or ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query to match against resource names and IDs.",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a project file. Requires confirmation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": (
                                "Relative path to the file within the project."
                            ),
                        },
                        "content": {
                            "type": "string",
                            "description": "Content to write to the file.",
                        },
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_task",
                "description": "Modify attributes of an existing task.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_path": {
                            "type": "string",
                            "description": "Dotted path to the task (e.g. 'project.phase.task').",
                        },
                        "attributes": {
                            "type": "object",
                            "description": "Dictionary of attributes to update.",
                        },
                    },
                    "required": ["task_path", "attributes"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "add_task",
                "description": "Add a new task definition to the project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "parent_path": {
                            "type": "string",
                            "description": "Dotted path to the parent task (empty for root level).",
                        },
                        "task": {
                            "type": "object",
                            "description": (
                                "Task definition with task_id, name, effort, allocation."
                            ),
                        },
                    },
                    "required": ["task"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_resource",
                "description": "Modify attributes of an existing resource.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "resource_id": {
                            "type": "string",
                            "description": "The resource ID to update.",
                        },
                        "attributes": {
                            "type": "object",
                            "description": "Dictionary of attributes to update.",
                        },
                    },
                    "required": ["resource_id", "attributes"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_timesheet",
                "description": "Write or merge a timesheet entry for a resource and week.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "resource_id": {
                            "type": "string",
                            "description": "The resource ID for the timesheet.",
                        },
                        "week": {
                            "type": "string",
                            "description": (
                                "ISO date of the Monday (YYYY-MM-DD)."
                                " Defaults to current week."
                            ),
                        },
                        "entries": {
                            "type": "array",
                            "description": (
                                "List of task entries with task_path, hours,"
                                " and optional status."
                            ),
                            "items": {
                                "type": "object",
                                "properties": {
                                    "task_path": {"type": "string"},
                                    "hours": {"type": "number"},
                                    "status_color": {"type": "string"},
                                    "status_headline": {"type": "string"},
                                    "status_summary": {"type": "string"},
                                },
                                "required": ["task_path", "hours"],
                            },
                        },
                    },
                    "required": ["resource_id", "entries"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_journal",
                "description": "Write a journal entry for a task or the project.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_path": {
                            "type": "string",
                            "description": "Dotted task path to attach the entry to (optional).",
                        },
                        "date": {
                            "type": "string",
                            "description": "Entry date in YYYY-MM-DD format (defaults to today).",
                        },
                        "author": {
                            "type": "string",
                            "description": "Author resource ID.",
                        },
                        "headline": {
                            "type": "string",
                            "description": "Headline text (max 120 characters).",
                        },
                        "summary": {
                            "type": "string",
                            "description": "Optional summary text.",
                        },
                    },
                    "required": ["headline"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_report",
                "description": "Write a TaskJuggler report definition.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "report_id": {
                            "type": "string",
                            "description": "Unique identifier for the report.",
                        },
                        "report_type": {
                            "type": "string",
                            "description": (
                                "Report type: taskreport, resourcereport,"
                                " accountreport, textreport, statusreport."
                            ),
                        },
                        "config": {
                            "type": "object",
                            "description": (
                                "Report configuration with title, columns,"
                                " formats, etc."
                            ),
                        },
                    },
                    "required": ["report_id", "report_type"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "compile_project",
                "description": "Run the tj3 compiler against the project and return the result.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_tj_docs",
                "description": (
                    "Search the bundled TaskJuggler reference documentation"
                    " for syntax and usage information."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for TaskJuggler documentation.",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
    ]


class ChatService:
    """Manages conversation flow and LM Studio communication.

    Orchestrates the full message lifecycle: building the system prompt,
    sending messages to LM Studio via the OpenAI-compatible API, handling
    tool call loops, and returning structured responses.

    Args:
        settings: Chat configuration settings.
        tool_executor: Executor for handling LLM tool calls.
    """

    def __init__(self, settings: ChatSettings, tool_executor: ToolExecutor) -> None:
        self._settings = settings
        self._tool_executor = tool_executor
        self._conversation = ConversationManager(token_limit=settings.token_limit)
        self._client = AsyncOpenAI(
            base_url=settings.lm_studio_url,
            api_key="lm-studio",  # LM Studio doesn't require a real key
        )
        self._model_name: str | None = settings.model_name
        self._system_prompt: str = ""
        self._tj_docs: TJDocumentationService | None = None
        self._confirm_fn: ConfirmFn = _default_confirm

    @property
    def confirm_fn(self) -> ConfirmFn:
        """The confirmation callback for write operations."""
        return self._confirm_fn

    @confirm_fn.setter
    def confirm_fn(self, fn: ConfirmFn) -> None:
        """Set the confirmation callback for write operations."""
        self._confirm_fn = fn

    @property
    def tj_docs(self) -> TJDocumentationService | None:
        """The TJ documentation service instance."""
        return self._tj_docs

    @tj_docs.setter
    def tj_docs(self, service: TJDocumentationService | None) -> None:
        """Set the TJ documentation service instance."""
        self._tj_docs = service

    async def connect(self) -> ConnectionResult:
        """Verify connectivity to LM Studio by querying the models endpoint.

        Sends a request to the models endpoint with a 10-second timeout.
        If a model_name is configured, uses it directly. Otherwise, selects
        the first model from the available models list.

        Returns:
            ConnectionResult indicating success/failure and the selected model.
        """
        try:
            models_response = await self._client.models.list(
                timeout=self._settings.connection_timeout,
            )

            # Extract model IDs - handle both standard OpenAI response
            # and LM Studio's potentially different format
            model_ids: list[str] = []
            try:
                # Standard openai library: response has .data attribute
                data = models_response.data if hasattr(models_response, "data") else list(models_response)
                for model in data:
                    if hasattr(model, "id"):
                        model_ids.append(model.id)
                    elif isinstance(model, dict) and "id" in model:
                        model_ids.append(model["id"])
                    elif isinstance(model, str):
                        model_ids.append(model)
            except (TypeError, AttributeError):
                pass

            if self._settings.model_name:
                self._model_name = self._settings.model_name
            elif model_ids:
                self._model_name = model_ids[0]
            else:
                return ConnectionResult(
                    success=False,
                    error="No models available in LM Studio.",
                )

            logger.info("Connected to LM Studio, using model: %s", self._model_name)
            return ConnectionResult(
                success=True,
                model_name=self._model_name,
            )

        except Exception as e:
            error_msg = (
                f"Failed to connect to LM Studio at {self._settings.lm_studio_url}: {e}"
            )
            logger.error(error_msg)
            return ConnectionResult(
                success=False,
                error=error_msg,
            )

    async def send_message(self, user_input: str) -> AgentResponse:
        """Send a user message and get the agent's response.

        Orchestrates the full message flow:
        1. Add user message to conversation history
        2. Build messages list with system prompt
        3. Call LM Studio chat completions API
        4. If tool calls are returned, execute them and loop
        5. Return the final text response

        Args:
            user_input: The user's message text.

        Returns:
            AgentResponse with the final text and any tool actions taken.
        """
        # Add user message to conversation
        self._conversation.add_message(Message(role="user", content=user_input))

        tool_actions: list[ToolAction] = []
        iterations = 0

        while iterations < _MAX_TOOL_ITERATIONS:
            iterations += 1

            # Build messages for the API call
            messages = self._conversation.truncate_to_limit(self._system_prompt)
            messages_dicts = [self._message_to_dict(m) for m in messages]

            # Call LM Studio
            try:
                response = await self._client.chat.completions.create(
                    model=self._model_name or "",
                    messages=messages_dicts,  # type: ignore[arg-type]
                    tools=_build_tool_definitions(),  # type: ignore[arg-type]
                    timeout=self._settings.response_timeout,
                )
            except Exception as e:
                error_text = f"Error communicating with LM Studio: {e}"
                logger.error(error_text)
                # Add error as assistant message to preserve context
                self._conversation.add_message(
                    Message(role="assistant", content=error_text)
                )
                return AgentResponse(text=error_text, tool_actions=tool_actions)

            choice = response.choices[0]
            assistant_message = choice.message

            # Check for tool calls
            if assistant_message.tool_calls:
                # Store the assistant message with tool calls in conversation
                tool_call_messages = [
                    ToolCallMessage(
                        id=tc.id,
                        type=tc.type or "function",
                        function=FunctionCall(
                            name=tc.function.name,
                            arguments=tc.function.arguments,
                        ),
                    )
                    for tc in assistant_message.tool_calls
                ]
                self._conversation.add_message(
                    Message(
                        role="assistant",
                        content=assistant_message.content,
                        tool_calls=tool_call_messages,
                    )
                )

                # Execute each tool call
                for tc in assistant_message.tool_calls:
                    try:
                        arguments = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                    parsed_call = ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )

                    result = await self._tool_executor.execute(
                        parsed_call, self._confirm_fn
                    )

                    # Record tool action summary
                    summary = result.content[:100] if result.content else ""
                    tool_actions.append(
                        ToolAction(tool_name=parsed_call.name, summary=summary)
                    )

                    # Add tool result to conversation
                    self._conversation.add_message(
                        Message(
                            role="tool",
                            content=result.content,
                            tool_call_id=tc.id,
                            name=tc.function.name,
                        )
                    )

                # Continue the loop to get the next response from the LLM
                continue

            # No tool calls — this is the final text response
            final_text = assistant_message.content or ""
            self._conversation.add_message(
                Message(role="assistant", content=final_text)
            )
            return AgentResponse(text=final_text, tool_actions=tool_actions)

        # Exceeded max iterations — return what we have
        fallback_text = (
            "I've reached the maximum number of tool call iterations. "
            "Here's what I've done so far. Please let me know if you'd like me to continue."
        )
        self._conversation.add_message(Message(role="assistant", content=fallback_text))
        return AgentResponse(text=fallback_text, tool_actions=tool_actions)

    async def reset_session(self) -> None:
        """Clear conversation history and start a fresh session."""
        self._conversation.clear()
        logger.info("Chat session reset.")

    def set_system_prompt(self, project_summary: ProjectSummary) -> None:
        """Build and cache the system prompt from project summary.

        Args:
            project_summary: Summary of the project structure.
        """
        self._system_prompt = build_system_prompt(
            project_summary, self._tj_docs
        )

    @staticmethod
    def _message_to_dict(message: Message) -> dict:
        """Convert a Message model to a dict suitable for the OpenAI API.

        Args:
            message: The message to convert.

        Returns:
            Dictionary representation for the API.
        """
        result: dict = {"role": message.role}

        if message.content is not None:
            result["content"] = message.content

        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        if message.tool_call_id is not None:
            result["tool_call_id"] = message.tool_call_id

        if message.name is not None:
            result["name"] = message.name

        return result


async def _default_confirm(summary: str) -> bool:
    """Default confirmation function that auto-accepts all operations.

    In production, this is replaced by the UI's confirmation dialog.

    Args:
        summary: Description of the proposed operation.

    Returns:
        Always True (auto-accept).
    """
    return True
