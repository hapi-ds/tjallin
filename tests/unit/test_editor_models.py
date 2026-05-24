"""Unit tests for editor data models and utility functions."""

from tj_chat.editor_models import (
    DiffSuggestion,
    EditorContext,
    FileContent,
    FileNode,
    HelperResponse,
    SaveResult,
    apply_suggestion,
    classify_file_type,
    truncate_path_display,
)


class TestClassifyFileType:
    """Tests for the file type classifier."""

    def test_tjp_extension(self) -> None:
        assert classify_file_type("project.tjp") == "tjp"

    def test_tji_extension(self) -> None:
        assert classify_file_type("includes/tasks.tji") == "tji"

    def test_other_extension(self) -> None:
        assert classify_file_type("readme.md") == "other"

    def test_no_extension(self) -> None:
        assert classify_file_type("Makefile") == "other"

    def test_dot_only(self) -> None:
        assert classify_file_type(".gitignore") == "other"

    def test_multiple_dots_tjp(self) -> None:
        assert classify_file_type("my.project.tjp") == "tjp"

    def test_multiple_dots_tji(self) -> None:
        assert classify_file_type("tasks.v2.tji") == "tji"

    def test_case_sensitive_tjp(self) -> None:
        # Extensions are case-sensitive; .TJP is not .tjp
        assert classify_file_type("project.TJP") == "other"

    def test_empty_string(self) -> None:
        assert classify_file_type("") == "other"


class TestTruncatePathDisplay:
    """Tests for the path display truncation utility."""

    def test_short_path_unchanged(self) -> None:
        path = "src/project.tjp"
        assert truncate_path_display(path) == path

    def test_exactly_60_chars_unchanged(self) -> None:
        path = "a" * 60
        assert truncate_path_display(path) == path

    def test_61_chars_truncated(self) -> None:
        path = "a" * 61
        result = truncate_path_display(path)
        assert len(result) <= 60
        assert result.startswith("…")

    def test_long_path_preserves_filename(self) -> None:
        path = "very/long/directory/structure/that/exceeds/sixty/characters/file.tjp"
        result = truncate_path_display(path)
        assert len(result) <= 60
        assert result.endswith("file.tjp")
        assert result.startswith("…")

    def test_long_path_with_backslashes(self) -> None:
        path = "very\\long\\directory\\structure\\that\\exceeds\\sixty\\characters\\file.tjp"
        result = truncate_path_display(path)
        assert len(result) <= 60
        assert result.endswith("file.tjp")
        assert result.startswith("…")

    def test_empty_string(self) -> None:
        assert truncate_path_display("") == ""

    def test_result_max_60_chars(self) -> None:
        path = "a/b/c/d/e/f/g/h/i/j/k/l/m/n/o/p/q/r/s/t/u/v/w/x/y/z/file.tjp"
        result = truncate_path_display(path)
        assert len(result) <= 60


class TestFileNode:
    """Tests for the FileNode model."""

    def test_defaults(self) -> None:
        node = FileNode(name="test.tjp", path="test.tjp", is_directory=False)
        assert node.children == []
        assert node.file_type == "other"

    def test_directory_with_children(self) -> None:
        child = FileNode(name="task.tji", path="sub/task.tji", is_directory=False, file_type="tji")
        parent = FileNode(name="sub", path="sub", is_directory=True, children=[child])
        assert len(parent.children) == 1
        assert parent.children[0].file_type == "tji"

    def test_file_type_literal(self) -> None:
        node = FileNode(name="p.tjp", path="p.tjp", is_directory=False, file_type="tjp")
        assert node.file_type == "tjp"


class TestFileContent:
    """Tests for the FileContent model."""

    def test_success(self) -> None:
        fc = FileContent(path="test.tjp", content="project x", success=True)
        assert fc.error is None

    def test_failure(self) -> None:
        fc = FileContent(path="bad.tjp", content="", success=False, error="Permission denied")
        assert fc.error == "Permission denied"


class TestSaveResult:
    """Tests for the SaveResult model."""

    def test_success(self) -> None:
        sr = SaveResult(success=True, backup_path="test.tjp.bak")
        assert sr.errors == []

    def test_failure(self) -> None:
        sr = SaveResult(success=False, errors=["line 5: syntax error"])
        assert sr.backup_path is None


class TestEditorContext:
    """Tests for the EditorContext model."""

    def test_defaults(self) -> None:
        ctx = EditorContext()
        assert ctx.file_path is None
        assert ctx.file_content is None
        assert ctx.cursor_line == 0
        assert ctx.surrounding_lines == ""
        assert ctx.project_files == []

    def test_with_values(self) -> None:
        ctx = EditorContext(
            file_path="test.tjp",
            file_content="project x",
            cursor_line=5,
            surrounding_lines="line4\nline5\nline6",
            project_files=["test.tjp", "tasks.tji"],
        )
        assert ctx.cursor_line == 5
        assert len(ctx.project_files) == 2


class TestDiffSuggestion:
    """Tests for the DiffSuggestion model."""

    def test_defaults(self) -> None:
        ds = DiffSuggestion(
            file_path="test.tjp",
            start_line=1,
            end_line=3,
            original_content="old",
            suggested_content="new",
        )
        assert ds.status == "pending"

    def test_status_values(self) -> None:
        for status in ("pending", "accepted", "rejected", "outdated"):
            ds = DiffSuggestion(
                file_path="f.tjp",
                start_line=1,
                end_line=1,
                original_content="a",
                suggested_content="b",
                status=status,
            )
            assert ds.status == status


class TestHelperResponse:
    """Tests for the HelperResponse model."""

    def test_defaults(self) -> None:
        hr = HelperResponse(text="Here is help")
        assert hr.suggestions == []
        assert hr.error is None

    def test_with_suggestions(self) -> None:
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=1,
            end_line=2,
            original_content="old",
            suggested_content="new",
        )
        hr = HelperResponse(text="Try this:", suggestions=[suggestion])
        assert len(hr.suggestions) == 1


class TestApplySuggestion:
    """Tests for the apply_suggestion utility function."""

    def test_successful_replacement_single_line(self) -> None:
        """Replacing a single line when original content matches."""
        content = "line1\nline2\nline3"
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=2,
            end_line=2,
            original_content="line2",
            suggested_content="replaced",
        )
        result, success = apply_suggestion(content, suggestion)
        assert success is True
        assert result == "line1\nreplaced\nline3"

    def test_successful_replacement_multiple_lines(self) -> None:
        """Replacing multiple lines when original content matches."""
        content = "line1\nline2\nline3\nline4\nline5"
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=2,
            end_line=4,
            original_content="line2\nline3\nline4",
            suggested_content="new2\nnew3",
        )
        result, success = apply_suggestion(content, suggestion)
        assert success is True
        assert result == "line1\nnew2\nnew3\nline5"

    def test_conflict_detection_content_mismatch(self) -> None:
        """Returns unchanged content when line range doesn't match original."""
        content = "line1\nmodified\nline3"
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=2,
            end_line=2,
            original_content="line2",
            suggested_content="replaced",
        )
        result, success = apply_suggestion(content, suggestion)
        assert success is False
        assert result == content

    def test_first_line_replacement(self) -> None:
        """Replacing the first line of the file."""
        content = "first\nsecond\nthird"
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=1,
            end_line=1,
            original_content="first",
            suggested_content="new_first",
        )
        result, success = apply_suggestion(content, suggestion)
        assert success is True
        assert result == "new_first\nsecond\nthird"

    def test_last_line_replacement(self) -> None:
        """Replacing the last line of the file."""
        content = "first\nsecond\nthird"
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=3,
            end_line=3,
            original_content="third",
            suggested_content="new_third",
        )
        result, success = apply_suggestion(content, suggestion)
        assert success is True
        assert result == "first\nsecond\nnew_third"

    def test_replace_with_more_lines(self) -> None:
        """Replacing one line with multiple lines."""
        content = "line1\nline2\nline3"
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=2,
            end_line=2,
            original_content="line2",
            suggested_content="new_a\nnew_b\nnew_c",
        )
        result, success = apply_suggestion(content, suggestion)
        assert success is True
        assert result == "line1\nnew_a\nnew_b\nnew_c\nline3"

    def test_replace_with_fewer_lines(self) -> None:
        """Replacing multiple lines with a single line."""
        content = "line1\nline2\nline3\nline4"
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=2,
            end_line=3,
            original_content="line2\nline3",
            suggested_content="merged",
        )
        result, success = apply_suggestion(content, suggestion)
        assert success is True
        assert result == "line1\nmerged\nline4"

    def test_does_not_mutate_suggestion(self) -> None:
        """The function does not modify the suggestion object."""
        content = "line1\nline2\nline3"
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=2,
            end_line=2,
            original_content="line2",
            suggested_content="replaced",
        )
        apply_suggestion(content, suggestion)
        assert suggestion.status == "pending"

    def test_independence_multiple_suggestions(self) -> None:
        """Accepting one suggestion doesn't affect another's applicability."""
        content = "line1\nline2\nline3\nline4\nline5"
        suggestion_a = DiffSuggestion(
            file_path="test.tjp",
            start_line=2,
            end_line=2,
            original_content="line2",
            suggested_content="new2",
        )
        suggestion_b = DiffSuggestion(
            file_path="test.tjp",
            start_line=4,
            end_line=4,
            original_content="line4",
            suggested_content="new4",
        )
        # Apply first suggestion
        result, success_a = apply_suggestion(content, suggestion_a)
        assert success_a is True
        # Apply second suggestion to the updated content
        result2, success_b = apply_suggestion(result, suggestion_b)
        assert success_b is True
        assert result2 == "line1\nnew2\nline3\nnew4\nline5"

    def test_entire_file_replacement(self) -> None:
        """Replacing all lines in the file."""
        content = "line1\nline2\nline3"
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=1,
            end_line=3,
            original_content="line1\nline2\nline3",
            suggested_content="completely\nnew\ncontent\nhere",
        )
        result, success = apply_suggestion(content, suggestion)
        assert success is True
        assert result == "completely\nnew\ncontent\nhere"

    def test_single_line_file(self) -> None:
        """Applying a suggestion to a single-line file."""
        content = "only_line"
        suggestion = DiffSuggestion(
            file_path="test.tjp",
            start_line=1,
            end_line=1,
            original_content="only_line",
            suggested_content="new_only_line",
        )
        result, success = apply_suggestion(content, suggestion)
        assert success is True
        assert result == "new_only_line"
