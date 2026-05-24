"""Unit tests for the conversation manager module."""

import pytest

from tj_chat.conversation import ConversationManager
from tj_chat.models import Message


@pytest.fixture
def manager() -> ConversationManager:
    """Create a ConversationManager with a generous token limit."""
    return ConversationManager(token_limit=4096)


@pytest.fixture
def small_limit_manager() -> ConversationManager:
    """Create a ConversationManager with a small token limit for truncation tests."""
    return ConversationManager(token_limit=100, min_recent_exchanges=4)


class TestAddMessage:
    """Tests for add_message()."""

    def test_single_message(self, manager: ConversationManager) -> None:
        msg = Message(role="user", content="Hello")
        manager.add_message(msg)
        messages = manager.get_messages("system")
        assert len(messages) == 2  # system + 1 user
        assert messages[1] == msg

    def test_preserves_insertion_order(self, manager: ConversationManager) -> None:
        msgs = [
            Message(role="user", content="First"),
            Message(role="assistant", content="Response 1"),
            Message(role="user", content="Second"),
            Message(role="assistant", content="Response 2"),
        ]
        for msg in msgs:
            manager.add_message(msg)

        result = manager.get_messages("sys")
        # Skip system message at index 0
        assert result[1:] == msgs

    def test_multiple_roles(self, manager: ConversationManager) -> None:
        manager.add_message(Message(role="user", content="Hi"))
        manager.add_message(Message(role="assistant", content="Hello!"))
        manager.add_message(Message(role="tool", content="result", tool_call_id="tc1"))

        result = manager.get_messages("sys")
        assert len(result) == 4
        assert result[1].role == "user"
        assert result[2].role == "assistant"
        assert result[3].role == "tool"


class TestGetMessages:
    """Tests for get_messages()."""

    def test_empty_history_returns_system_only(self, manager: ConversationManager) -> None:
        result = manager.get_messages("You are a helpful assistant.")
        assert len(result) == 1
        assert result[0].role == "system"
        assert result[0].content == "You are a helpful assistant."

    def test_system_prompt_is_first(self, manager: ConversationManager) -> None:
        manager.add_message(Message(role="user", content="Hi"))
        result = manager.get_messages("System prompt here")
        assert result[0].role == "system"
        assert result[0].content == "System prompt here"

    def test_history_follows_system_prompt(self, manager: ConversationManager) -> None:
        manager.add_message(Message(role="user", content="A"))
        manager.add_message(Message(role="assistant", content="B"))
        result = manager.get_messages("sys")
        assert result[1].content == "A"
        assert result[2].content == "B"


class TestEstimateTokens:
    """Tests for estimate_tokens()."""

    def test_empty_list(self, manager: ConversationManager) -> None:
        assert manager.estimate_tokens([]) == 0

    def test_single_message(self, manager: ConversationManager) -> None:
        # 20 chars / 4 = 5 tokens
        msg = Message(role="user", content="a" * 20)
        assert manager.estimate_tokens([msg]) == 5

    def test_multiple_messages(self, manager: ConversationManager) -> None:
        msgs = [
            Message(role="user", content="a" * 40),  # 10 tokens
            Message(role="assistant", content="b" * 80),  # 20 tokens
        ]
        assert manager.estimate_tokens(msgs) == 30

    def test_none_content_contributes_zero(self, manager: ConversationManager) -> None:
        msg = Message(role="assistant", content=None)
        assert manager.estimate_tokens([msg]) == 0

    def test_chars_div_4_truncates(self, manager: ConversationManager) -> None:
        # 7 chars / 4 = 1 (integer division)
        msg = Message(role="user", content="abcdefg")
        assert manager.estimate_tokens([msg]) == 1


class TestClear:
    """Tests for clear()."""

    def test_clear_empties_history(self, manager: ConversationManager) -> None:
        manager.add_message(Message(role="user", content="Hello"))
        manager.add_message(Message(role="assistant", content="Hi"))
        manager.clear()
        result = manager.get_messages("sys")
        assert len(result) == 1  # Only system prompt

    def test_clear_allows_new_messages(self, manager: ConversationManager) -> None:
        manager.add_message(Message(role="user", content="Old"))
        manager.clear()
        manager.add_message(Message(role="user", content="New"))
        result = manager.get_messages("sys")
        assert len(result) == 2
        assert result[1].content == "New"


class TestTruncateToLimit:
    """Tests for truncate_to_limit()."""

    def test_within_limit_returns_all(self, manager: ConversationManager) -> None:
        manager.add_message(Message(role="user", content="Hi"))
        manager.add_message(Message(role="assistant", content="Hello"))
        result = manager.truncate_to_limit("sys")
        assert len(result) == 3  # system + 2 messages

    def test_preserves_system_prompt(self, small_limit_manager: ConversationManager) -> None:
        # Add many messages to exceed limit
        for i in range(20):
            small_limit_manager.add_message(
                Message(role="user", content=f"Message {i} " + "x" * 50)
            )
            small_limit_manager.add_message(
                Message(role="assistant", content=f"Reply {i} " + "y" * 50)
            )
        result = small_limit_manager.truncate_to_limit("System prompt")
        assert result[0].role == "system"
        assert result[0].content == "System prompt"

    def test_preserves_minimum_recent_exchanges(self) -> None:
        # Very small limit to force truncation
        mgr = ConversationManager(token_limit=50, min_recent_exchanges=2)
        for i in range(10):
            mgr.add_message(Message(role="user", content=f"User {i}"))
            mgr.add_message(Message(role="assistant", content=f"Bot {i}"))

        result = mgr.truncate_to_limit("s")
        # Should have system + at least 4 messages (2 exchanges)
        non_system = [m for m in result if m.role != "system"]
        assert len(non_system) >= 4

        # The last 4 messages should be the most recent 2 exchanges
        assert non_system[-1].content == "Bot 9"
        assert non_system[-2].content == "User 9"
        assert non_system[-3].content == "Bot 8"
        assert non_system[-4].content == "User 8"

    def test_fewer_messages_than_minimum_returns_all(self) -> None:
        mgr = ConversationManager(token_limit=50, min_recent_exchanges=4)
        mgr.add_message(Message(role="user", content="Hi"))
        mgr.add_message(Message(role="assistant", content="Hello"))
        result = mgr.truncate_to_limit("sys")
        assert len(result) == 3  # system + 2

    def test_truncation_removes_oldest_first(self) -> None:
        # Each message ~100 chars = 25 tokens. 20 messages = 500 tokens.
        # System prompt ~10 tokens. Total ~510. Limit 200 forces truncation.
        mgr = ConversationManager(token_limit=200, min_recent_exchanges=2)
        for i in range(10):
            mgr.add_message(Message(role="user", content=f"User msg {i} " + "x" * 88))
            mgr.add_message(Message(role="assistant", content=f"Bot msg {i} " + "y" * 89))

        result = mgr.truncate_to_limit("system prompt text here")

        # Verify oldest messages are removed
        contents = [m.content for m in result if m.role != "system"]
        # Should not contain the earliest messages (they were truncated)
        assert not any("User msg 0" in c for c in contents if c)
        # Should contain the latest messages (preserved as recent exchanges)
        assert any("Bot msg 9" in c for c in contents if c)
        assert any("User msg 9" in c for c in contents if c)
