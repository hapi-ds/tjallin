"""Property-based tests for conversation manager and system prompt builder.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4, 13.3, 13.4**

Property 11: Conversation history preserves message order.
- For any sequence of messages added to the conversation manager, retrieving
  the history SHALL return messages in the same order they were added
  (insertion order preserved).

Property 12: Conversation truncation respects token limit and preserves recent context.
- For any conversation history that exceeds the configured token limit, the
  truncated result SHALL: (a) not exceed the token limit, (b) include the
  system prompt, and (c) include at minimum the 4 most recent exchanges
  (user message + assistant response pairs).

Property 13: System prompt contains project structure, tool names, and TJ syntax reference.
- For any ProjectSummary containing file names, resource IDs, and task names,
  the generated system prompt SHALL contain all file names from the project tree,
  all tool names from the tool registry, descriptions of include file purposes,
  and (when documentation is available) a condensed TaskJuggler syntax reference
  covering key constructs.
"""

from __future__ import annotations

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tj_chat.conversation import ConversationManager
from tj_chat.models import Message, ProjectSummary
from tj_chat.system_prompt import (
    INCLUDE_FILE_DESCRIPTIONS,
    TOOL_NAMES,
    build_system_prompt,
)

# Strategy for message roles (excluding "system" since that's managed separately)
_role = st.sampled_from(["user", "assistant", "tool"])

# Strategy for message content: non-empty printable text
_content = st.text(
    alphabet=st.characters(categories=("L", "N", "Z", "P")),
    min_size=1,
    max_size=200,
).filter(lambda s: s.strip() != "")

# Strategy for a single message
_message = st.builds(
    Message,
    role=_role,
    content=_content,
)

# Strategy for a list of messages (1 to 30 messages)
_message_list = st.lists(_message, min_size=1, max_size=30)

# Strategy for system prompt text
_system_prompt = st.text(
    alphabet=st.characters(categories=("L", "N", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip() != "")

# Strategy for token limits (reasonable range)
_token_limit = st.integers(min_value=100, max_value=10000)

# Strategy for exchanges: pairs of (user, assistant) messages
_exchange = st.tuples(
    st.builds(Message, role=st.just("user"), content=_content),
    st.builds(Message, role=st.just("assistant"), content=_content),
)

# Strategy for a list of exchanges (4 to 20 exchanges to ensure we exceed limits)
_exchange_list = st.lists(_exchange, min_size=4, max_size=20)


class TestConversationHistoryOrderProperty:
    """Property 11: Conversation history preserves message order.

    **Validates: Requirements 6.1**
    """

    @given(messages=_message_list, system_prompt=_system_prompt)
    @settings(max_examples=100)
    def test_messages_returned_in_insertion_order(
        self, messages: list[Message], system_prompt: str
    ) -> None:
        """Messages retrieved from history are in the same order they were added."""
        manager = ConversationManager(token_limit=100000)

        for msg in messages:
            manager.add_message(msg)

        result = manager.get_messages(system_prompt)

        # First message should be the system prompt
        assert result[0].role == "system"
        assert result[0].content == system_prompt

        # Remaining messages should match insertion order
        history = result[1:]
        assert len(history) == len(messages), (
            f"Expected {len(messages)} history messages, got {len(history)}"
        )

        for i, (returned, original) in enumerate(zip(history, messages)):
            assert returned.role == original.role, (
                f"Message {i}: role mismatch. "
                f"Expected {original.role!r}, got {returned.role!r}"
            )
            assert returned.content == original.content, (
                f"Message {i}: content mismatch. "
                f"Expected {original.content!r}, got {returned.content!r}"
            )

    @given(messages=_message_list, system_prompt=_system_prompt)
    @settings(max_examples=100)
    def test_order_preserved_after_multiple_additions(
        self, messages: list[Message], system_prompt: str
    ) -> None:
        """Adding messages one at a time preserves their relative order."""
        manager = ConversationManager(token_limit=100000)

        # Add messages one by one and verify order is maintained
        for i, msg in enumerate(messages):
            manager.add_message(msg)
            result = manager.get_messages(system_prompt)
            # Skip system prompt at index 0
            current_history = result[1:]
            assert len(current_history) == i + 1
            assert current_history[-1].content == msg.content
            assert current_history[-1].role == msg.role


class TestConversationTruncationProperty:
    """Property 12: Conversation truncation respects token limit and preserves recent context.

    **Validates: Requirements 6.2, 6.3**
    """

    @given(
        exchanges=_exchange_list,
        system_prompt=_system_prompt,
    )
    @settings(max_examples=100)
    def test_truncation_does_not_exceed_token_limit(
        self, exchanges: list[tuple[Message, Message]], system_prompt: str
    ) -> None:
        """Truncated result does not exceed the configured token limit."""
        # Use a small token limit to force truncation
        # Estimate: each message ~50 chars = ~12 tokens, system prompt ~25 tokens
        # With 4+ exchanges (8+ messages), a limit of 200 should force truncation
        token_limit = 200

        manager = ConversationManager(token_limit=token_limit)

        for user_msg, assistant_msg in exchanges:
            manager.add_message(user_msg)
            manager.add_message(assistant_msg)

        result = manager.truncate_to_limit(system_prompt)
        estimated_tokens = manager.estimate_tokens(result)

        # The result should not exceed the token limit
        # (unless the minimum preserved messages alone exceed it,
        # in which case the minimum is still preserved)
        min_preserved = 4 * 2  # 4 exchanges = 8 messages
        if len(exchanges) > 4:
            # Only assert token limit when we have more than minimum exchanges
            # (if minimum alone exceeds limit, the property still holds for
            # the "preserve recent context" part)
            min_messages = [Message(role="system", content=system_prompt)]
            for user_msg, assistant_msg in exchanges[-4:]:
                min_messages.extend([user_msg, assistant_msg])
            min_tokens = manager.estimate_tokens(min_messages)

            if min_tokens <= token_limit:
                assert estimated_tokens <= token_limit, (
                    f"Truncated result ({estimated_tokens} tokens) exceeds "
                    f"token limit ({token_limit})"
                )

    @given(
        exchanges=_exchange_list,
        system_prompt=_system_prompt,
    )
    @settings(max_examples=100)
    def test_truncation_includes_system_prompt(
        self, exchanges: list[tuple[Message, Message]], system_prompt: str
    ) -> None:
        """Truncated result always includes the system prompt as first message."""
        token_limit = 200

        manager = ConversationManager(token_limit=token_limit)

        for user_msg, assistant_msg in exchanges:
            manager.add_message(user_msg)
            manager.add_message(assistant_msg)

        result = manager.truncate_to_limit(system_prompt)

        assert len(result) >= 1, "Truncated result should not be empty"
        assert result[0].role == "system", (
            f"First message should be system prompt, got role={result[0].role!r}"
        )
        assert result[0].content == system_prompt, (
            f"System prompt content mismatch"
        )

    @given(
        exchanges=_exchange_list,
        system_prompt=_system_prompt,
    )
    @settings(max_examples=100)
    def test_truncation_preserves_at_least_four_recent_exchanges(
        self, exchanges: list[tuple[Message, Message]], system_prompt: str
    ) -> None:
        """Truncated result preserves at minimum the 4 most recent exchanges."""
        assume(len(exchanges) >= 4)

        token_limit = 200

        manager = ConversationManager(token_limit=token_limit)

        for user_msg, assistant_msg in exchanges:
            manager.add_message(user_msg)
            manager.add_message(assistant_msg)

        result = manager.truncate_to_limit(system_prompt)

        # Remove system prompt to get just the history messages
        history = result[1:]

        # Should have at least 8 messages (4 exchanges * 2 messages each)
        assert len(history) >= 8, (
            f"Expected at least 8 messages (4 exchanges), got {len(history)}"
        )

        # The last 8 messages should correspond to the last 4 exchanges
        last_4_exchanges = exchanges[-4:]
        expected_tail: list[Message] = []
        for user_msg, assistant_msg in last_4_exchanges:
            expected_tail.append(user_msg)
            expected_tail.append(assistant_msg)

        actual_tail = history[-8:]

        for i, (actual, expected) in enumerate(zip(actual_tail, expected_tail)):
            assert actual.role == expected.role, (
                f"Recent exchange message {i}: role mismatch. "
                f"Expected {expected.role!r}, got {actual.role!r}"
            )
            assert actual.content == expected.content, (
                f"Recent exchange message {i}: content mismatch. "
                f"Expected {expected.content!r}, got {actual.content!r}"
            )



# --- Strategies for Property 13 ---

# Strategy for file names (non-empty, no newlines, resembling file paths)
_file_name = st.text(
    alphabet=st.characters(categories=("L", "N"), whitelist_characters="._-/"),
    min_size=3,
    max_size=40,
).filter(lambda s: s.strip() != "" and "/" not in s[:1])

# Strategy for resource IDs (simple identifiers)
_resource_id = st.from_regex(r"[a-z][a-z0-9_]{1,15}", fullmatch=True)

# Strategy for task names (simple identifiers)
_task_name = st.from_regex(r"[a-z][a-z0-9_.]{1,20}", fullmatch=True)

# Strategy for a ProjectSummary with non-empty lists
_project_summary = st.builds(
    ProjectSummary,
    project_name=st.text(
        alphabet=st.characters(categories=("L", "N", "Z")),
        min_size=1,
        max_size=30,
    ).filter(lambda s: s.strip() != ""),
    start_date=st.just("2024-01-01"),
    end_date=st.just("2024-12-31"),
    now_date=st.just("2024-06-15"),
    file_tree=st.lists(_file_name, min_size=1, max_size=10),
    resource_ids=st.lists(_resource_id, min_size=1, max_size=5),
    top_level_tasks=st.lists(_task_name, min_size=1, max_size=5),
)


class _FakeTJDocsService:
    """Fake TJ documentation service for testing with docs available."""

    def __init__(self, available: bool = True) -> None:
        self._available = available

    @property
    def is_available(self) -> bool:
        return self._available

    def get_syntax_reference(self) -> str:
        if not self._available:
            return ""
        return (
            "# TaskJuggler Syntax Reference\n\n"
            "## task\n\n```\ntask id \"name\" { }\n```\n\n"
            "## resource\n\n```\nresource id \"name\" { }\n```"
        )


class TestSystemPromptContentProperty:
    """Property 13: System prompt contains project structure, tool names, and TJ syntax reference.

    **Validates: Requirements 6.4, 13.3, 13.4**
    """

    @given(project_summary=_project_summary)
    @settings(max_examples=100)
    def test_system_prompt_contains_all_file_names(
        self, project_summary: ProjectSummary
    ) -> None:
        """System prompt contains all file names from the project tree."""
        prompt = build_system_prompt(project_summary)

        for file_name in project_summary.file_tree:
            assert file_name in prompt, (
                f"File name {file_name!r} not found in system prompt"
            )

    @given(project_summary=_project_summary)
    @settings(max_examples=100)
    def test_system_prompt_contains_all_tool_names(
        self, project_summary: ProjectSummary
    ) -> None:
        """System prompt contains all tool names from the tool registry."""
        prompt = build_system_prompt(project_summary)

        for tool_name in TOOL_NAMES:
            assert tool_name in prompt, (
                f"Tool name {tool_name!r} not found in system prompt"
            )

    @given(project_summary=_project_summary)
    @settings(max_examples=100)
    def test_system_prompt_contains_include_file_descriptions(
        self, project_summary: ProjectSummary
    ) -> None:
        """System prompt contains descriptions of include file purposes."""
        prompt = build_system_prompt(project_summary)

        for filename, description in INCLUDE_FILE_DESCRIPTIONS.items():
            assert filename in prompt, (
                f"Include file name {filename!r} not found in system prompt"
            )
            assert description in prompt, (
                f"Include file description {description!r} not found in system prompt"
            )

    @given(project_summary=_project_summary)
    @settings(max_examples=100)
    def test_system_prompt_contains_syntax_reference_when_docs_available(
        self, project_summary: ProjectSummary
    ) -> None:
        """System prompt contains TJ syntax reference when documentation is available."""
        docs_service = _FakeTJDocsService(available=True)
        prompt = build_system_prompt(project_summary, tj_docs_service=docs_service)

        assert "TaskJuggler Syntax Reference" in prompt, (
            "System prompt should contain TJ syntax reference when docs are available"
        )
        assert "task" in prompt
        assert "resource" in prompt

    @given(project_summary=_project_summary)
    @settings(max_examples=100)
    def test_system_prompt_omits_syntax_reference_when_docs_unavailable(
        self, project_summary: ProjectSummary
    ) -> None:
        """System prompt omits TJ syntax reference when documentation is unavailable."""
        docs_service = _FakeTJDocsService(available=False)
        prompt = build_system_prompt(project_summary, tj_docs_service=docs_service)

        assert "TaskJuggler Syntax Reference" not in prompt, (
            "System prompt should NOT contain TJ syntax reference when docs are unavailable"
        )
