"""Property-based tests for diff suggestion parsing.

# Feature: project-file-editor, Property 10: Diff suggestion parsing

**Validates: Requirements 6.1**

For any LLM response text containing a fenced code block annotated with
a file path and line range (in the expected format), the response parser
SHALL extract exactly one DiffSuggestion per annotated block with the
correct file path, start line, end line, and suggested content.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.editor_models import EditorContext
from tj_chat.helper_service import parse_diff_suggestions


# Strategy for valid file path segments (no whitespace, no backticks)
_path_segment = st.text(
    alphabet=st.characters(
        categories=("L", "N"),
        exclude_characters="\x00 \t\n\r`",
    ),
    min_size=1,
    max_size=15,
)

# Strategy for a valid file path like "dir/subdir/file.tjp"
_file_path = st.builds(
    lambda parts, ext: "/".join(parts) + ext,
    parts=st.lists(_path_segment, min_size=1, max_size=4),
    ext=st.sampled_from([".tjp", ".tji", ".py", ".txt", ""]),
)

# Strategy for line numbers (start <= end, both positive)
_line_range = st.tuples(
    st.integers(min_value=1, max_value=500),
    st.integers(min_value=1, max_value=500),
).map(lambda t: (min(t), max(t)) if t[0] != t[1] else (t[0], t[0] + 1))

# Strategy for code content (no triple backticks to avoid breaking the block)
_code_content = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "Z"),
        exclude_characters="`\x00",
    ),
    min_size=1,
    max_size=100,
).filter(lambda s: "```" not in s and s.strip() != "")


def _build_annotated_block(file_path: str, start: int, end: int, content: str) -> str:
    """Build a single annotated fenced code block in the expected format."""
    return f"```tj path={file_path} lines={start}-{end}\n{content}\n```"


# Strategy for a single annotated block with its expected fields
_annotated_block = st.builds(
    lambda fp, lr, c: (fp, lr[0], lr[1], c, _build_annotated_block(fp, lr[0], lr[1], c)),
    fp=_file_path,
    lr=_line_range,
    c=_code_content,
)

# Strategy for surrounding prose text (no triple backticks)
_prose_text = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "Z"),
        exclude_characters="`\x00",
    ),
    min_size=0,
    max_size=80,
).filter(lambda s: "```" not in s)


class TestDiffSuggestionParsing:
    """Property 10: Diff suggestion parsing.

    **Validates: Requirements 6.1**
    """

    @given(block=_annotated_block)
    @settings(max_examples=100)
    def test_single_block_extracts_one_suggestion(
        self,
        block: tuple[str, int, int, str, str],
    ) -> None:
        """A single annotated block produces exactly one DiffSuggestion."""
        file_path, start, end, content, block_text = block
        context = EditorContext()

        suggestions = parse_diff_suggestions(block_text, context)

        assert len(suggestions) == 1
        assert suggestions[0].file_path == file_path
        assert suggestions[0].start_line == start
        assert suggestions[0].end_line == end
        assert suggestions[0].suggested_content == content

    @given(
        blocks=st.lists(_annotated_block, min_size=1, max_size=5),
        prose=_prose_text,
    )
    @settings(max_examples=100)
    def test_multiple_blocks_extract_correct_count(
        self,
        blocks: list[tuple[str, int, int, str, str]],
        prose: str,
    ) -> None:
        """N annotated blocks produce exactly N DiffSuggestions."""
        # Build response text with prose between blocks
        response_parts = []
        for _fp, _start, _end, _content, block_text in blocks:
            response_parts.append(prose)
            response_parts.append(block_text)
        response_parts.append(prose)
        response_text = "\n".join(response_parts)

        context = EditorContext()
        suggestions = parse_diff_suggestions(response_text, context)

        assert len(suggestions) == len(blocks)

    @given(
        blocks=st.lists(_annotated_block, min_size=1, max_size=5),
        prose=_prose_text,
    )
    @settings(max_examples=100)
    def test_each_block_has_correct_fields(
        self,
        blocks: list[tuple[str, int, int, str, str]],
        prose: str,
    ) -> None:
        """Each DiffSuggestion has the correct file_path, start_line, end_line, and suggested_content."""
        response_parts = []
        for _fp, _start, _end, _content, block_text in blocks:
            response_parts.append(prose)
            response_parts.append(block_text)
        response_parts.append(prose)
        response_text = "\n".join(response_parts)

        context = EditorContext()
        suggestions = parse_diff_suggestions(response_text, context)

        for i, (file_path, start, end, content, _block_text) in enumerate(blocks):
            assert suggestions[i].file_path == file_path
            assert suggestions[i].start_line == start
            assert suggestions[i].end_line == end
            assert suggestions[i].suggested_content == content

    @given(prose=_prose_text)
    @settings(max_examples=100)
    def test_no_annotated_blocks_returns_empty(self, prose: str) -> None:
        """Text without annotated blocks produces no DiffSuggestions."""
        context = EditorContext()
        suggestions = parse_diff_suggestions(prose, context)

        assert suggestions == []


# Feature: project-file-editor, Property 11: Diff suggestion application


class TestDiffSuggestionApplication:
    """Property 11: Diff suggestion application.

    **Validates: Requirements 6.3**

    For any valid DiffSuggestion where the editor content at the referenced
    line range matches the suggestion's original_content, accepting the
    suggestion SHALL replace exactly those lines with the suggested_content,
    leaving all other lines unchanged.
    """

    @given(data=st.data())
    @settings(max_examples=100)
    def test_accepting_valid_suggestion_replaces_lines(self, data: st.DataObject) -> None:
        """Accepting a valid suggestion replaces exactly the referenced lines."""
        from tj_chat.editor_models import DiffSuggestion, apply_suggestion

        # Generate multi-line content (at least 3 lines)
        num_lines = data.draw(st.integers(min_value=3, max_value=20), label="num_lines")
        lines = data.draw(
            st.lists(
                st.text(
                    alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\n\r\x00"),
                    min_size=1,
                    max_size=40,
                ),
                min_size=num_lines,
                max_size=num_lines,
            ),
            label="lines",
        )

        # Generate a valid line range within the content (1-indexed)
        start_line = data.draw(st.integers(min_value=1, max_value=num_lines), label="start_line")
        end_line = data.draw(st.integers(min_value=start_line, max_value=num_lines), label="end_line")

        # Build the content string
        content = "\n".join(lines)

        # The original_content must match the lines at the range
        original_content = "\n".join(lines[start_line - 1 : end_line])

        # Generate random suggested content (replacement)
        suggested_lines = data.draw(
            st.lists(
                st.text(
                    alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\n\r\x00"),
                    min_size=0,
                    max_size=40,
                ),
                min_size=1,
                max_size=5,
            ),
            label="suggested_lines",
        )
        suggested_content = "\n".join(suggested_lines)

        suggestion = DiffSuggestion(
            file_path="test/file.tjp",
            start_line=start_line,
            end_line=end_line,
            original_content=original_content,
            suggested_content=suggested_content,
        )

        new_content, success = apply_suggestion(content, suggestion)

        # Must succeed
        assert success is True

        # Verify the result
        new_lines = new_content.split("\n")
        original_lines = content.split("\n")

        # Lines before start_line are unchanged
        assert new_lines[: start_line - 1] == original_lines[: start_line - 1]

        # Lines after end_line are unchanged
        assert new_lines[start_line - 1 + len(suggested_lines) :] == original_lines[end_line:]

        # The lines at start_line to end_line are replaced with suggested_content
        replaced_section = new_lines[start_line - 1 : start_line - 1 + len(suggested_lines)]
        assert replaced_section == suggested_lines


# ---------------------------------------------------------------------------
# Feature: project-file-editor, Property 12: Diff suggestion conflict detection
# ---------------------------------------------------------------------------


from tj_chat.editor_models import DiffSuggestion, apply_suggestion


# Strategy for multi-line content (at least 2 lines to allow a valid range)
_multiline_content = st.lists(
    st.text(
        alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\x00\n"),
        min_size=1,
        max_size=40,
    ),
    min_size=2,
    max_size=20,
).map(lambda lines: "\n".join(lines))


# Strategy for a line range within content (1-indexed, start <= end)
@st.composite
def _content_with_conflicting_suggestion(draw: st.DrawFn) -> tuple[str, DiffSuggestion]:
    """Generate content and a DiffSuggestion whose original_content does NOT match the lines at the range."""
    content_lines = draw(
        st.lists(
            st.text(
                alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\x00\n"),
                min_size=1,
                max_size=40,
            ),
            min_size=2,
            max_size=20,
        )
    )
    content = "\n".join(content_lines)
    num_lines = len(content_lines)

    # Pick a valid line range (1-indexed)
    start_line = draw(st.integers(min_value=1, max_value=num_lines))
    end_line = draw(st.integers(min_value=start_line, max_value=num_lines))

    # Extract the actual content at that range
    actual_at_range = "\n".join(content_lines[start_line - 1 : end_line])

    # Generate original_content that is DIFFERENT from what's actually at the range
    different_content = draw(
        st.text(
            alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\x00"),
            min_size=1,
            max_size=80,
        ).filter(lambda s: s != actual_at_range)
    )

    # Generate some suggested content (doesn't matter what it is for this test)
    suggested_content = draw(
        st.text(
            alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\x00"),
            min_size=1,
            max_size=80,
        )
    )

    file_path = draw(_file_path)

    suggestion = DiffSuggestion(
        file_path=file_path,
        start_line=start_line,
        end_line=end_line,
        original_content=different_content,
        suggested_content=suggested_content,
    )

    return (content, suggestion)


class TestDiffSuggestionConflictDetection:
    """Property 12: Diff suggestion conflict detection.

    **Validates: Requirements 6.4**

    For any DiffSuggestion where the editor content at the referenced line range
    does NOT match the suggestion's original_content, attempting to accept the
    suggestion SHALL leave the editor content entirely unchanged and return False
    (the caller is responsible for marking the suggestion as "outdated").
    """

    @given(data=_content_with_conflicting_suggestion())
    @settings(max_examples=100)
    def test_conflict_leaves_content_unchanged(
        self,
        data: tuple[str, DiffSuggestion],
    ) -> None:
        """When original_content doesn't match the line range, content is unchanged."""
        content, suggestion = data

        result_content, success = apply_suggestion(content, suggestion)

        # The function should return False (conflict detected)
        assert success is False
        # The content must be returned completely unchanged
        assert result_content == content


# Feature: project-file-editor, Property 13: Diff suggestion independence


class TestDiffSuggestionIndependence:
    """Property 13: Diff suggestion independence.

    **Validates: Requirements 6.7**

    For any set of multiple DiffSuggestion instances with non-overlapping
    line ranges, accepting or rejecting one suggestion SHALL not change the
    status or availability of any other suggestion.
    """

    @given(data=st.data())
    @settings(max_examples=100)
    def test_applying_one_suggestion_does_not_affect_others(
        self,
        data: st.DataObject,
    ) -> None:
        """Applying any single suggestion independently succeeds on the original content.

        This proves independence: each suggestion can be applied on its own
        without being affected by the application of another.
        """
        from tj_chat.editor_models import DiffSuggestion, apply_suggestion

        # Generate multi-line content (20-50 lines)
        num_lines = data.draw(st.integers(min_value=20, max_value=50), label="num_lines")
        lines = data.draw(
            st.lists(
                st.text(
                    alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\n\x00"),
                    min_size=1,
                    max_size=40,
                ),
                min_size=num_lines,
                max_size=num_lines,
            ),
            label="lines",
        )
        content = "\n".join(lines)

        # Generate 2-4 non-overlapping suggestion ranges
        num_suggestions = data.draw(st.integers(min_value=2, max_value=4), label="num_suggestions")

        # Partition lines into non-overlapping ranges for suggestions
        # Each suggestion needs at least 1 line, and we need gaps between them
        # to ensure non-overlapping. Use a simple approach: divide available lines.
        available_lines = num_lines
        min_per_suggestion = 2  # at least 2 lines per suggestion (1 for content + 1 gap)

        # Only proceed if we have enough lines for all suggestions
        if available_lines < num_suggestions * min_per_suggestion:
            return  # Not enough lines, skip this example

        # Generate non-overlapping ranges by picking sorted start points
        # with minimum spacing
        segment_size = available_lines // num_suggestions
        ranges: list[tuple[int, int]] = []
        for i in range(num_suggestions):
            seg_start = i * segment_size
            seg_end = (i + 1) * segment_size - 1  # leave gap of at least 1 line
            if seg_start >= seg_end:
                return  # degenerate case, skip
            # Pick a range within this segment (1-indexed)
            start_1 = seg_start + 1  # 1-indexed
            end_1 = seg_end + 1  # 1-indexed, inclusive
            # Draw a sub-range within [start_1, end_1]
            actual_start = data.draw(
                st.integers(min_value=start_1, max_value=end_1),
                label=f"range_{i}_start",
            )
            actual_end = data.draw(
                st.integers(min_value=actual_start, max_value=end_1),
                label=f"range_{i}_end",
            )
            ranges.append((actual_start, actual_end))

        # Build DiffSuggestion instances with original_content matching actual content
        suggestions: list[DiffSuggestion] = []
        for i, (start, end) in enumerate(ranges):
            original_lines = lines[start - 1 : end]  # 0-indexed slice
            original_content = "\n".join(original_lines)
            # Generate replacement content
            suggested_content = data.draw(
                st.text(
                    alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\n\x00"),
                    min_size=1,
                    max_size=40,
                ),
                label=f"suggested_{i}",
            )
            suggestions.append(
                DiffSuggestion(
                    file_path=f"test_{i}.tjp",
                    start_line=start,
                    end_line=end,
                    original_content=original_content,
                    suggested_content=suggested_content,
                    status="pending",
                )
            )

        # Property: each suggestion can be applied independently on the original content
        for suggestion in suggestions:
            new_content, success = apply_suggestion(content, suggestion)
            assert success, (
                f"Suggestion for lines {suggestion.start_line}-{suggestion.end_line} "
                f"failed to apply independently on original content"
            )
            # Verify the suggestion status was not mutated by apply_suggestion
            assert suggestion.status == "pending"

    @given(data=st.data())
    @settings(max_examples=100)
    def test_applying_one_does_not_change_content_at_other_ranges(
        self,
        data: st.DataObject,
    ) -> None:
        """After applying suggestion A, the content at suggestion B's range is unchanged (B before A).

        For non-overlapping suggestions where B's range comes before A's range,
        applying A does not shift B's lines, so B's original content is preserved.
        """
        from tj_chat.editor_models import DiffSuggestion, apply_suggestion

        # Generate content with enough lines for 2 non-overlapping suggestions
        num_lines = data.draw(st.integers(min_value=10, max_value=30), label="num_lines")
        lines = data.draw(
            st.lists(
                st.text(
                    alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\n\x00"),
                    min_size=1,
                    max_size=30,
                ),
                min_size=num_lines,
                max_size=num_lines,
            ),
            label="lines",
        )
        content = "\n".join(lines)

        # Split into two halves for two non-overlapping suggestions
        mid = num_lines // 2
        if mid < 2 or num_lines - mid < 2:
            return  # Not enough room

        # Suggestion B: in the first half (lines 1..mid-1)
        b_start = data.draw(st.integers(min_value=1, max_value=max(1, mid - 1)), label="b_start")
        b_end = data.draw(st.integers(min_value=b_start, max_value=max(b_start, mid - 1)), label="b_end")

        # Suggestion A: in the second half (lines mid+1..num_lines)
        a_start = data.draw(st.integers(min_value=mid + 1, max_value=num_lines), label="a_start")
        a_end = data.draw(st.integers(min_value=a_start, max_value=num_lines), label="a_end")

        # Build suggestions with matching original_content
        b_original = "\n".join(lines[b_start - 1 : b_end])
        a_original = "\n".join(lines[a_start - 1 : a_end])

        suggested_b = data.draw(
            st.text(
                alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\n\x00"),
                min_size=1,
                max_size=30,
            ),
            label="suggested_b",
        )
        suggested_a = data.draw(
            st.text(
                alphabet=st.characters(categories=("L", "N", "P", "Z"), exclude_characters="\n\x00"),
                min_size=1,
                max_size=30,
            ),
            label="suggested_a",
        )

        suggestion_b = DiffSuggestion(
            file_path="b.tjp",
            start_line=b_start,
            end_line=b_end,
            original_content=b_original,
            suggested_content=suggested_b,
        )
        suggestion_a = DiffSuggestion(
            file_path="a.tjp",
            start_line=a_start,
            end_line=a_end,
            original_content=a_original,
            suggested_content=suggested_a,
        )

        # Apply suggestion A (later range) — B's range (earlier) should be unaffected
        new_content, success_a = apply_suggestion(content, suggestion_a)
        assert success_a

        # Verify B's content at its range is unchanged in the new content
        new_lines = new_content.split("\n")
        b_content_after = "\n".join(new_lines[b_start - 1 : b_end])
        assert b_content_after == b_original, (
            "Applying suggestion A changed content at suggestion B's range"
        )

        # B should still be applicable on the modified content at its original position
        new_content_2, success_b = apply_suggestion(new_content, suggestion_b)
        assert success_b, (
            "Suggestion B could not be applied after suggestion A was applied"
        )
