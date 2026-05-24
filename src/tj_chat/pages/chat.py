"""Chat page with message history, input, and confirmation dialogs.

Provides the browser-based conversational interface for the LLM agent,
including message display, loading indicators, tool action summaries,
write confirmation dialogs, and graceful degradation when LM Studio
is unreachable.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from nicegui import ui

if TYPE_CHECKING:
    from tj_chat.chat_service import ChatService
    from tj_chat.tj_docs import TJDocumentationService

logger = logging.getLogger(__name__)


class ChatPageUI:
    """Chat page with message history, input, and confirmation dialogs.

    Displays a scrollable message area with visually distinct message types,
    a text input for user messages, a loading spinner during processing,
    tool action summaries as system messages, and Accept/Decline buttons
    for write confirmations.

    On page load, attempts to connect to LM Studio. If the connection fails,
    displays a prominent error banner with the endpoint URL, error message,
    and a retry button. The message input is disabled while disconnected.

    Args:
        chat_service: The chat service instance for sending messages.
        tj_docs: Optional TJ documentation service to check availability.
    """

    def __init__(
        self,
        chat_service: ChatService,
        tj_docs: TJDocumentationService | None = None,
    ) -> None:
        self._chat_service = chat_service
        self._tj_docs = tj_docs
        self._processing: bool = False
        self._connected: bool = False
        self._pending_confirmation: asyncio.Future[bool] | None = None

    def setup(self) -> None:
        """Render the chat page UI components."""
        with ui.column().classes("w-full max-w-4xl mx-auto h-[calc(100vh-80px)] p-4"):
            # Degraded mode banner when TJ docs are unavailable
            if self._tj_docs is not None and not self._tj_docs.is_available:
                with ui.banner().classes("w-full bg-amber-100 text-amber-900"):
                    ui.icon("warning").classes("text-amber-700")
                    ui.label(
                        "Enhanced TaskJuggler syntax support is unavailable. "
                        "The bundled documentation could not be loaded."
                    )

            # Connection error banner (hidden by default, shown on connection failure)
            self._connection_banner = ui.column().classes("w-full hidden")
            with self._connection_banner:
                with ui.banner().classes(
                    "w-full bg-red-100 text-red-900 border border-red-300"
                ):
                    with ui.row().classes("items-center gap-2 w-full"):
                        ui.icon("error").classes("text-red-700 text-xl")
                        with ui.column().classes("flex-grow gap-1"):
                            ui.label("Unable to connect to LM Studio").classes(
                                "font-bold"
                            )
                            self._connection_error_label = ui.label("").classes(
                                "text-sm"
                            )
                            self._connection_endpoint_label = ui.label("").classes(
                                "text-xs text-red-700 font-mono"
                            )
                        ui.button(
                            "Retry",
                            on_click=self._retry_connection,
                            icon="refresh",
                        ).props("flat color=negative")

            # Scrollable message area
            self._scroll_area = ui.scroll_area().classes(
                "w-full flex-grow border rounded-lg bg-grey-1 p-4"
            )
            with self._scroll_area:
                self._messages_container = ui.column().classes(
                    "w-full gap-2"
                )

            # Loading spinner (hidden by default)
            self._spinner_row = ui.row().classes(
                "w-full justify-center py-2 hidden"
            )
            with self._spinner_row:
                ui.spinner("dots", size="md")
                ui.label("Agent is thinking...").classes("text-grey-6 ml-2")

            # Input area
            with ui.row().classes("w-full gap-2 mt-2"):
                self._input = ui.input(
                    placeholder="Type a message...",
                ).classes("flex-grow").props(
                    'outlined dense'
                ).on("keydown.enter", self._on_send)
                self._send_button = ui.button(
                    icon="send",
                    on_click=self._on_send,
                ).props("flat round color=primary")

        # Attempt connection on page load
        ui.timer(0.1, self._check_connection, once=True)

    async def _check_connection(self) -> None:
        """Attempt to connect to LM Studio and update UI state accordingly."""
        result = await self._chat_service.connect()
        if result.success:
            self._connected = True
            self._connection_banner.classes(add="hidden")
            self._input.props(remove="disable")
            self._send_button.props(remove="disable")
        else:
            self._connected = False
            endpoint_url = self._chat_service._settings.lm_studio_url
            error_msg = result.error or "Connection failed"
            self._connection_error_label.text = error_msg
            self._connection_endpoint_label.text = f"Endpoint: {endpoint_url}"
            self._connection_banner.classes(remove="hidden")
            self._input.props(add="disable")
            self._send_button.props(add="disable")

    async def _retry_connection(self) -> None:
        """Retry the connection to LM Studio when the user clicks Retry."""
        await self._check_connection()

    async def _on_send(self) -> None:
        """Handle sending a message from the input field."""
        if not self._connected:
            return

        text = self._input.value
        if not text or not text.strip():
            return

        self._input.value = ""
        await self.send_message(text.strip())

    async def send_message(self, text: str) -> None:
        """Send a user message and display the agent's response.

        Args:
            text: The user's message text.
        """
        if self._processing:
            return

        # Display user message
        self._display_user_message(text)

        # Show loading spinner
        self._processing = True
        self._spinner_row.classes(remove="hidden")

        try:
            # Set up confirmation callback
            self._chat_service.confirm_fn = self._handle_confirmation

            # Send message to chat service
            response = await self._chat_service.send_message(text)

            # Display tool actions as system messages
            for action in response.tool_actions:
                self.display_tool_action(action.tool_name, action.summary)

            # Display agent response
            if response.text:
                self.display_agent_message(response.text)

            # Handle confirmation request if present
            if response.confirmation_request:
                await self._show_confirmation_inline(
                    response.confirmation_request.description
                )

        except Exception as e:
            logger.error("Error sending message: %s", e)
            self.display_system_message(f"Error: {e}")
        finally:
            self._processing = False
            self._spinner_row.classes(add="hidden")
            self._scroll_to_bottom()

    def _display_user_message(self, text: str) -> None:
        """Display a user message (right-aligned, blue background).

        Args:
            text: The message text.
        """
        with self._messages_container:
            with ui.row().classes("w-full justify-end"):
                ui.chat_message(
                    text=text,
                    sent=True,
                ).classes("max-w-[70%]")
        self._scroll_to_bottom()

    def display_agent_message(self, text: str) -> None:
        """Display an agent response message (left-aligned).

        Args:
            text: The agent's response text.
        """
        with self._messages_container:
            with ui.row().classes("w-full justify-start"):
                ui.chat_message(
                    text=text,
                    sent=False,
                    name="Agent",
                    stamp="🤖",
                ).classes("max-w-[70%]")
        self._scroll_to_bottom()

    def display_tool_action(self, tool_name: str, summary: str) -> None:
        """Display a tool action summary as a system message.

        Shows the tool name and a one-line summary in a distinct style.

        Args:
            tool_name: Name of the tool that was executed.
            summary: One-line summary of the action taken.
        """
        with self._messages_container:
            with ui.row().classes("w-full justify-center"):
                with ui.card().classes(
                    "bg-blue-grey-1 px-3 py-1 text-caption text-grey-7"
                ):
                    ui.label(f"🔧 {tool_name}: {summary}").classes(
                        "text-xs italic"
                    )
        self._scroll_to_bottom()

    def display_system_message(self, text: str) -> None:
        """Display a system message (centered, grey styling).

        Args:
            text: The system message text.
        """
        with self._messages_container:
            with ui.row().classes("w-full justify-center"):
                ui.label(text).classes(
                    "text-sm text-grey-6 italic bg-grey-2 px-3 py-1 rounded"
                )
        self._scroll_to_bottom()

    async def show_confirmation(self, summary: str) -> bool:
        """Show a confirmation dialog and wait for user response.

        This is used as the confirm_fn callback for the chat service.

        Args:
            summary: Description of the proposed write operation.

        Returns:
            True if the user accepts, False if they decline.
        """
        return await self._show_confirmation_inline(summary)

    async def _show_confirmation_inline(self, summary: str) -> bool:
        """Display Accept/Decline buttons inline in the conversation.

        Args:
            summary: Description of the proposed write operation.

        Returns:
            True if accepted, False if declined.
        """
        self._pending_confirmation = asyncio.get_event_loop().create_future()

        with self._messages_container:
            with ui.card().classes(
                "w-full bg-amber-50 border-l-4 border-amber-500 p-3"
            ):
                ui.label("✍️ Write Confirmation Required").classes(
                    "text-bold text-amber-900"
                )
                ui.label(summary).classes("text-sm text-grey-8 mt-1")
                with ui.row().classes("gap-2 mt-2"):
                    ui.button(
                        "Accept",
                        on_click=lambda: self._resolve_confirmation(True),
                        icon="check",
                    ).props("color=positive flat")
                    ui.button(
                        "Decline",
                        on_click=lambda: self._resolve_confirmation(False),
                        icon="close",
                    ).props("color=negative flat")

        self._scroll_to_bottom()

        try:
            result = await self._pending_confirmation
        except asyncio.CancelledError:
            result = False
        finally:
            self._pending_confirmation = None

        # Display the decision as a system message
        decision_text = "✓ Change accepted" if result else "✗ Change declined"
        self.display_system_message(decision_text)

        return result

    def _resolve_confirmation(self, accepted: bool) -> None:
        """Resolve the pending confirmation future.

        Args:
            accepted: Whether the user accepted the change.
        """
        if self._pending_confirmation and not self._pending_confirmation.done():
            self._pending_confirmation.set_result(accepted)

    async def _handle_confirmation(self, summary: str) -> bool:
        """Confirmation callback for the chat service.

        Args:
            summary: Description of the proposed operation.

        Returns:
            True if accepted, False if declined.
        """
        return await self._show_confirmation_inline(summary)

    def _scroll_to_bottom(self) -> None:
        """Scroll the message area to the bottom."""
        self._scroll_area.scroll_to(percent=1.0)
