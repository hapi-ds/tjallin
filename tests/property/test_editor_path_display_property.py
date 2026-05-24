"""Property-based tests for path display truncation.

# Feature: project-file-editor, Property 4: Path display truncation

**Validates: Requirements 3.4**

Property 4: Path display truncation
- For any file path string, the display formatter SHALL return a string of at most
  60 characters.
- If the original path exceeds 60 characters, the result SHALL end with the file
  name portion and begin with an ellipsis ("…").
- If the original path is 60 characters or fewer, it SHALL be returned unchanged.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.editor_models import truncate_path_display

# Strategy for path characters (printable, no null bytes)
_path_char = st.characters(
    categories=("L", "N", "P", "S"),
    exclude_characters="\x00",
)

# Strategy for arbitrary path strings of varying lengths
_any_path = st.text(alphabet=_path_char, min_size=0, max_size=200)

# Strategy for paths that are guaranteed to exceed 60 characters
_long_path_segment = st.text(alphabet=_path_char, min_size=1, max_size=30).filter(
    lambda s: s.strip() != ""
)


@st.composite
def long_path_with_separator(draw: st.DrawFn) -> str:
    """Generate a path longer than 60 chars that contains a path separator.

    Ensures the path has a recognizable filename portion after the last separator.
    """
    # Build a path with multiple segments separated by / or \\
    sep = draw(st.sampled_from(["/", "\\"]))
    num_segments = draw(st.integers(min_value=3, max_value=8))
    segments = [draw(_long_path_segment) for _ in range(num_segments)]
    path = sep.join(segments)
    # Ensure it exceeds 60 chars by padding if needed
    while len(path) <= 60:
        path = draw(_long_path_segment) + sep + path
    return path


@st.composite
def short_path(draw: st.DrawFn) -> str:
    """Generate a path of at most 60 characters."""
    path = draw(st.text(alphabet=_path_char, min_size=0, max_size=60))
    return path


class TestPathDisplayTruncation:
    """Property 4: Path display truncation.

    **Validates: Requirements 3.4**
    """

    @given(path=_any_path)
    @settings(max_examples=200)
    def test_result_never_exceeds_max_length(self, path: str) -> None:
        """For any path string, the result is always ≤ 60 characters."""
        result = truncate_path_display(path)
        assert len(result) <= 60, (
            f"Result length {len(result)} exceeds 60 for input of length {len(path)}"
        )

    @given(path=short_path())
    @settings(max_examples=200)
    def test_short_paths_returned_unchanged(self, path: str) -> None:
        """If the original path is 60 characters or fewer, it is returned unchanged."""
        assert len(path) <= 60  # Precondition
        result = truncate_path_display(path)
        assert result == path, (
            f"Path of length {len(path)} should be returned unchanged"
        )

    @given(path=long_path_with_separator())
    @settings(max_examples=200)
    def test_long_paths_start_with_ellipsis(self, path: str) -> None:
        """If the original path exceeds 60 characters, the result starts with '…'."""
        assert len(path) > 60  # Precondition
        result = truncate_path_display(path)
        assert result.startswith("…"), (
            f"Truncated path should start with ellipsis, got: {result!r}"
        )

    @given(path=long_path_with_separator())
    @settings(max_examples=200)
    def test_long_paths_end_with_filename(self, path: str) -> None:
        """If the original path exceeds 60 characters, the result ends with the filename."""
        assert len(path) > 60  # Precondition

        # Extract filename (last component after last separator)
        sep_idx = max(path.rfind("/"), path.rfind("\\"))
        if sep_idx == -1:
            filename = path
        else:
            filename = path[sep_idx + 1:]

        result = truncate_path_display(path)
        assert result.endswith(filename) or (
            # If filename itself is too long, the result is a truncated version
            len(filename) + 1 >= 60
        ), f"Result {result!r} should end with filename {filename!r}"

    @given(path=_any_path)
    @settings(max_examples=200)
    def test_result_length_within_max_length_with_custom_max(self, path: str) -> None:
        """For any path and default max_length=60, result ≤ 60 chars."""
        result = truncate_path_display(path, max_length=60)
        assert len(result) <= 60
