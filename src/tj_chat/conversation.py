"""Conversation history management with token-aware truncation.

Maintains ordered message history for multi-turn LLM conversations,
with automatic truncation when token limits are exceeded.
"""

from __future__ import annotations

from tj_chat.models import Message


class ConversationManager:
    """Maintains conversation history with token limit management.

    Preserves insertion order of messages and provides token-aware
    truncation that keeps the system prompt and recent exchanges.

    Args:
        token_limit: Maximum token budget for conversation history.
        min_recent_exchanges: Minimum number of recent user+assistant
            pairs to preserve during truncation (default 4).
    """

    def __init__(self, token_limit: int, min_recent_exchanges: int = 4) -> None:
        self._token_limit = token_limit
        self._min_recent_exchanges = min_recent_exchanges
        self._messages: list[Message] = []

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation history.

        Messages are stored in insertion order.

        Args:
            message: The message to append to history.
        """
        self._messages.append(message)

    def get_messages(self, system_prompt: str) -> list[Message]:
        """Return the full message history with system prompt prepended.

        Args:
            system_prompt: The system prompt text to include as the
                first message.

        Returns:
            List starting with the system prompt message followed by
            all history messages in insertion order.
        """
        system_message = Message(role="system", content=system_prompt)
        return [system_message, *self._messages]

    def truncate_to_limit(self, system_prompt: str) -> list[Message]:
        """Truncate history to fit within the token limit.

        Removes oldest messages first while always preserving:
        - The system prompt (prepended)
        - At minimum the most recent `min_recent_exchanges` exchanges
          (user+assistant pairs = min_recent_exchanges * 2 messages)

        Args:
            system_prompt: The system prompt text to include.

        Returns:
            The truncated message list fitting within the token limit.
        """
        system_message = Message(role="system", content=system_prompt)

        # Minimum messages to preserve from the end of history
        min_preserved_count = self._min_recent_exchanges * 2

        # If history is within the preserved minimum, return everything
        if len(self._messages) <= min_preserved_count:
            result = [system_message, *self._messages]
            return result

        # Try with all messages first
        full_result = [system_message, *self._messages]
        if self.estimate_tokens(full_result) <= self._token_limit:
            return full_result

        # Binary-style removal: drop oldest messages until within limit,
        # but always keep at least min_preserved_count from the end
        preserved_tail = self._messages[-min_preserved_count:]

        # Start with just system + preserved tail, then add back older
        # messages from most recent to oldest until we hit the limit
        remaining_older = self._messages[:-min_preserved_count]

        # Try adding older messages back from newest to oldest
        included_older: list[Message] = []
        for msg in reversed(remaining_older):
            candidate = [system_message, *([msg] + included_older), *preserved_tail]
            if self.estimate_tokens(candidate) <= self._token_limit:
                included_older.insert(0, msg)
            else:
                break

        result = [system_message, *included_older, *preserved_tail]

        # Update internal history to match truncated state
        self._messages = [*included_older, *preserved_tail]

        return result

    def estimate_tokens(self, messages: list[Message]) -> int:
        """Estimate token count for a list of messages.

        Uses a chars/4 approximation for each message's content.

        Args:
            messages: List of messages to estimate tokens for.

        Returns:
            Estimated total token count across all messages.
        """
        total = 0
        for msg in messages:
            if msg.content:
                total += len(msg.content) // 4
        return total

    def clear(self) -> None:
        """Reset the conversation history to empty."""
        self._messages = []
