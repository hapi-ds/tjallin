"""Helper service for the editor's inline agentic assistant panel.

Manages LLM interactions with editor-specific context, including file content,
cursor position, project file list, and TJ documentation search results.
Maintains a separate conversation history from the main chat page.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import httpx
from openai import AsyncOpenAI

from tj_chat.editor_models import DiffSuggestion, EditorContext, HelperResponse
from tj_chat.settings import ChatSettings

if TYPE_CHECKING:
    from tj_chat.tj_docs import TJDocumentationService

logger = logging.getLogger(__name__)

# Timeout for LLM requests in seconds
_LLM_TIMEOUT = 120

# Pattern to match annotated fenced code blocks:
# ```tj path=<file_path> lines=<start>-<end>
# <content>
# ```
_DIFF_BLOCK_PATTERN = re.compile(
    r"```tj\s+path=(?P<file_path>\S+)\s+lines=(?P<start>\d+)-(?P<end>\d+)\s*\n"
    r"(?P<content>.*?)\n```",
    re.DOTALL,
)

_SYSTEM_PROMPT = """\
You are a TaskJuggler syntax assistant embedded in a code editor. Your role is to help \
users write and fix TaskJuggler (.tjp and .tji) project files.

Guidelines:
- Provide concise, accurate TJ syntax assistance.
- When the user asks about syntax, explain with examples.
- When suggesting code changes, use annotated fenced code blocks with the file path \
and line range so the editor can present them as diffs.
- Format for code suggestions: ```tj path=<file_path> lines=<start>-<end>
<suggested_content>
```
- The line range indicates which lines in the original file should be replaced.
- Only suggest changes when the user asks for modifications or fixes.
- Use the provided file context and TJ documentation to ground your responses.
- Keep responses focused and relevant to the user's question.
"""


class HelperService:
    """Manages the agentic helper panel's LLM interactions with editor context.

    Maintains its own conversation history (independent of the main Chat page)
    with a specialized system prompt focused on TJ syntax assistance and
    diff-based suggestions.

    Args:
        settings: Chat configuration settings.
        tj_docs: Optional TJ documentation service for grounding responses.
    """

    def __init__(
        self,
        settings: ChatSettings,
        tj_docs: TJDocumentationService | None,
    ) -> None:
        self._settings = settings
        self._tj_docs = tj_docs
        self._client = AsyncOpenAI(
            base_url=settings.lm_studio_url,
            api_key="lm-studio",
        )
        self._model_name: str | None = settings.model_name
        self._history: list[dict[str, str]] = []

    async def send_message(
        self,
        user_message: str,
        context: EditorContext,
    ) -> HelperResponse:
        """Send a context-enriched message to the LLM.

        Builds a context string from the EditorContext, searches TJ documentation
        if available, constructs the message payload, and sends it to the LLM.
        Maintains conversation history across calls within the same session.

        Args:
            user_message: The user's question or request.
            context: Current editor context (file, cursor, project files).

        Returns:
            HelperResponse with the LLM's text and any parsed diff suggestions.
        """
        # Reject empty/whitespace-only input
        if not user_message.strip():
            return HelperResponse(
                text="",
                error="Empty input is not allowed.",
            )

        # Build context string
        context_str = self._build_context_string(context)

        # Search TJ documentation if available
        doc_context = ""
        if self._tj_docs is not None:
            doc_results = self._tj_docs.search(user_message)
            if doc_results:
                doc_sections = []
                for doc in doc_results[:3]:  # Limit to top 3 results
                    doc_sections.append(
                        f"### {doc.title}\n{doc.content}"
                    )
                doc_context = (
                    "\n\n## Relevant TJ Documentation:\n"
                    + "\n\n".join(doc_sections)
                )

        # Build the user message with context
        enriched_message = (
            f"{context_str}{doc_context}\n\n## User Question:\n{user_message}"
        )

        # Add to conversation history
        self._history.append({"role": "user", "content": enriched_message})

        # Build messages list
        messages: list[dict[str, str]] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            *self._history,
        ]

        # Send to LLM
        try:
            response = await self._client.chat.completions.create(
                model=self._model_name or "",
                messages=messages,  # type: ignore[arg-type]
                timeout=_LLM_TIMEOUT,
            )
        except httpx.TimeoutException:
            # Remove the failed message from history
            self._history.pop()
            return HelperResponse(
                text="",
                error="Request timed out. The LLM service did not respond within 120 seconds.",
            )
        except (httpx.ConnectError, httpx.NetworkError, OSError) as e:
            # Remove the failed message from history
            self._history.pop()
            logger.error("LLM service unreachable: %s", e)
            return HelperResponse(
                text="",
                error="The LLM service is unavailable. Please check that LM Studio is running.",
            )
        except Exception as e:
            # Remove the failed message from history
            self._history.pop()
            logger.error("Unexpected error communicating with LLM: %s", e)
            return HelperResponse(
                text="",
                error=f"Error communicating with the LLM service: {e}",
            )

        # Extract response text
        response_text = response.choices[0].message.content or ""

        # Add assistant response to history
        self._history.append({"role": "assistant", "content": response_text})

        # Parse diff suggestions from the response
        suggestions = parse_diff_suggestions(response_text, context)

        return HelperResponse(
            text=response_text,
            suggestions=suggestions,
        )

    def reset_session(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    @property
    def history(self) -> list[dict[str, str]]:
        """Return the current conversation history (read-only view)."""
        return list(self._history)

    def _build_context_string(self, context: EditorContext) -> str:
        """Build a context string from the EditorContext for the LLM.

        Includes file name, content, cursor line, surrounding lines,
        and project file list.

        Args:
            context: The current editor context.

        Returns:
            Formatted context string.
        """
        parts: list[str] = ["## Editor Context:"]

        if context.file_path:
            parts.append(f"**Current file:** {context.file_path}")

        if context.cursor_line > 0:
            parts.append(f"**Cursor at line:** {context.cursor_line}")

        if context.surrounding_lines:
            parts.append(
                f"**Surrounding lines (10 above/below cursor):**\n"
                f"```\n{context.surrounding_lines}\n```"
            )

        if context.file_content:
            parts.append(
                f"**Full file content:**\n```\n{context.file_content}\n```"
            )

        if context.project_files:
            file_list = "\n".join(f"- {f}" for f in context.project_files)
            parts.append(f"**Project files:**\n{file_list}")

        return "\n\n".join(parts)


def parse_diff_suggestions(
    response_text: str,
    context: EditorContext,
) -> list[DiffSuggestion]:
    """Parse annotated fenced code blocks from LLM response into DiffSuggestions.

    Looks for blocks in the format:
    ```tj path=<file_path> lines=<start>-<end>
    <suggested_content>
    ```

    For each match, extracts the original content from the editor context
    (if available) and builds a DiffSuggestion.

    Args:
        response_text: The raw LLM response text.
        context: The current editor context for extracting original content.

    Returns:
        List of parsed DiffSuggestion instances.
    """
    suggestions: list[DiffSuggestion] = []

    for match in _DIFF_BLOCK_PATTERN.finditer(response_text):
        file_path = match.group("file_path")
        start_line = int(match.group("start"))
        end_line = int(match.group("end"))
        suggested_content = match.group("content")

        # Extract original content from context if the file matches
        original_content = ""
        if context.file_content and context.file_path:
            if file_path == context.file_path:
                lines = context.file_content.splitlines()
                # Lines are 1-indexed in the annotation
                start_idx = max(0, start_line - 1)
                end_idx = min(len(lines), end_line)
                original_content = "\n".join(lines[start_idx:end_idx])

        suggestions.append(
            DiffSuggestion(
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                original_content=original_content,
                suggested_content=suggested_content,
            )
        )

    return suggestions
