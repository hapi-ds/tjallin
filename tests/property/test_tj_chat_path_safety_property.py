"""Property-based tests for path safety module.

**Validates: Requirements 7.3, 7.4, 7.5**

Property 1: Path security rejects out-of-bounds paths.
- For any file path that, when resolved to its canonical absolute form
  (resolving .., ., and symlinks), falls outside the configured project
  directory, the path validator SHALL reject the operation and raise a
  PathSecurityError.
- Conversely, paths resolving inside the project boundary never raise
  PathSecurityError.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tj_chat.models import PathSecurityError
from tj_chat.path_safety import validate_project_path

# Strategy for valid path segment characters (no null bytes, no path separators)
_path_char = st.characters(
    categories=("L", "N"),
    exclude_characters="\x00/\\:",
)

# Strategy for a single safe directory/file name segment
_safe_segment = st.text(alphabet=_path_char, min_size=1, max_size=12).filter(
    lambda s: s not in (".", "..", "") and s.strip() != ""
)


@st.composite
def path_inside_project(draw: st.DrawFn) -> str:
    """Generate a relative path that resolves inside the project root.

    Builds a path from 1-4 safe segments, ensuring it stays within bounds.
    """
    depth = draw(st.integers(min_value=1, max_value=4))
    segments = [draw(_safe_segment) for _ in range(depth)]
    return "/".join(segments)


@st.composite
def path_outside_via_dotdot(draw: st.DrawFn) -> tuple[str, int]:
    """Generate a relative path that escapes the project root using '..' segments.

    Returns the path string and the number of '..' segments used.
    The caller must ensure the project root has fewer depth levels than escape_count.
    """
    escape_count = draw(st.integers(min_value=5, max_value=10))
    target_segment = draw(_safe_segment)
    dotdots = "/".join([".."] * escape_count)
    return f"{dotdots}/{target_segment}", escape_count


@st.composite
def sibling_directory_name(draw: st.DrawFn) -> str:
    """Generate a safe directory name for use as a sibling of the project root."""
    return draw(_safe_segment)


class TestPathSecurityRejectsOutOfBounds:
    """Property 1: Path security rejects out-of-bounds paths.

    **Validates: Requirements 7.3, 7.4, 7.5**
    """

    @given(path_and_count=path_outside_via_dotdot())
    @settings(max_examples=100)
    def test_dotdot_escape_raises_path_security_error(
        self, path_and_count: tuple[str, int]
    ) -> None:
        """Paths using '..' to escape the project boundary always raise PathSecurityError."""
        path_str, escape_count = path_and_count

        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()

            # Verify the path actually resolves outside
            target = (project_root / path_str).resolve()
            canonical_root = project_root.resolve()
            try:
                target.relative_to(canonical_root)
                assume(False)  # Skip if it doesn't actually escape
            except ValueError:
                pass  # Good - it escapes

            with pytest.raises(PathSecurityError) as exc_info:
                validate_project_path(path_str, project_root)

            assert exc_info.value.path == path_str
            assert str(canonical_root) in exc_info.value.project_root

    @given(sibling=_safe_segment, extra=_safe_segment)
    @settings(max_examples=100)
    def test_absolute_path_outside_raises_path_security_error(
        self, sibling: str, extra: str
    ) -> None:
        """Absolute paths outside the project boundary always raise PathSecurityError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()

            # Create an absolute path in a sibling directory
            assume(sibling != "project")
            outside_path = Path(tmp_dir) / sibling / extra
            path_str = str(outside_path)

            # Verify the path actually resolves outside
            target = Path(path_str).resolve()
            canonical_root = project_root.resolve()
            try:
                target.relative_to(canonical_root)
                assume(False)
            except ValueError:
                pass

            with pytest.raises(PathSecurityError):
                validate_project_path(path_str, project_root)

    @given(rel_path=path_inside_project())
    @settings(max_examples=100)
    def test_path_inside_project_never_raises(self, rel_path: str) -> None:
        """Paths resolving inside the project boundary never raise PathSecurityError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()

            # This should NOT raise PathSecurityError
            result = validate_project_path(rel_path, project_root)

            # Verify the result is within the project root
            canonical_root = project_root.resolve()
            result.relative_to(canonical_root)  # Should not raise ValueError

    @given(safe_name=_safe_segment)
    @settings(max_examples=100)
    def test_dot_segments_inside_project_resolve_correctly(
        self, safe_name: str
    ) -> None:
        """Paths with '.' and '..' that still resolve inside the project are accepted."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()
            (project_root / "subdir").mkdir(exist_ok=True)

            # Generate a path like "subdir/../<safe_name>" which stays inside
            path_str = f"subdir/../{safe_name}"

            # This should NOT raise since it resolves to project_root/<safe_name>
            result = validate_project_path(path_str, project_root)

            canonical_root = project_root.resolve()
            result.relative_to(canonical_root)  # Should not raise ValueError

    @given(root_name=_safe_segment)
    @settings(max_examples=50)
    def test_project_root_itself_is_always_valid(self, root_name: str) -> None:
        """The project root path itself is always accepted."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / root_name
            project_root.mkdir(exist_ok=True)

            result = validate_project_path(str(project_root), project_root)
            assert result == project_root.resolve()
