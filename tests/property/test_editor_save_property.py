"""Property-based tests for EditorService save operations.

# Feature: project-file-editor, Property 7: Write path safety enforcement

**Validates: Requirements 4.6, 8.2, 8.3**

Property 7: Write path safety enforcement
- For any file path that resolves to a location outside the project directory
  boundary, the save operation SHALL reject the write and return a security
  error without modifying any file on disk.
"""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tj_chat.editor_models import SaveResult
from tj_chat.editor_service import EditorService
from tj_chat.settings import ChatSettings

# Strategy for valid path segment characters (no null bytes, no path separators)
_path_char = st.characters(
    categories=("L", "N"),
    exclude_characters="\x00/\\:",
)

# Strategy for a single safe directory/file name segment
_safe_segment = st.text(alphabet=_path_char, min_size=1, max_size=12).filter(
    lambda s: s not in (".", "..", "") and s.strip() != ""
)


# Strategy for file content that avoids line-ending normalization issues on Windows
# and excludes characters that can't be encoded to UTF-8 (surrogates, null bytes).
_safe_content = st.text(
    alphabet=st.characters(
        exclude_characters="\x00\r",
        exclude_categories=("Cs",),  # Exclude surrogates
    ),
    min_size=1,
    max_size=50,
)


@st.composite
def path_outside_via_dotdot(draw: st.DrawFn) -> str:
    """Generate a relative path that escapes the project root using '..' segments.

    Uses enough '..' segments to guarantee escape from any reasonable project depth.
    """
    escape_count = draw(st.integers(min_value=5, max_value=10))
    target_segment = draw(_safe_segment)
    dotdots = "/".join([".."] * escape_count)
    return f"{dotdots}/{target_segment}"


class TestWritePathSafetyEnforcement:
    """Property 7: Write path safety enforcement.

    # Feature: project-file-editor, Property 7: Write path safety enforcement

    **Validates: Requirements 4.6, 8.2, 8.3**

    For any path outside the project boundary, save rejects with security
    error and no file is modified.
    """

    @given(escape_path=path_outside_via_dotdot(), content=_safe_content)
    @settings(max_examples=100)
    def test_dotdot_escape_rejected_with_security_error(
        self, escape_path: str, content: str
    ) -> None:
        """Paths using '..' to escape the project boundary are rejected by save_file."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()

            # Verify the path actually resolves outside
            target = (project_root / escape_path).resolve()
            canonical_root = project_root.resolve()
            try:
                target.relative_to(canonical_root)
                assume(False)  # Skip if it doesn't actually escape
            except ValueError:
                pass  # Good - it escapes

            # Create settings with project_path
            mock_settings = ChatSettings(
                project_path=project_root,
            )

            service = EditorService(project_dir=project_root, settings=mock_settings)

            # Run save_file - should reject without modifying anything
            result: SaveResult = asyncio.run(
                service.save_file(escape_path, content)
            )

            # Verify: save rejected with security error
            assert result.success is False
            assert any("security" in err.lower() or "Security" in err for err in result.errors)

            # Verify: no files were created or modified outside project
            # The target path should not exist
            assert not target.exists(), (
                f"File was created outside project boundary at {target}"
            )

            # Verify: no temp files left in project directory
            project_files = list(project_root.iterdir())
            temp_files = [f for f in project_files if ".tmp" in f.name]
            assert len(temp_files) == 0, (
                f"Temp files left behind in project: {temp_files}"
            )

    @given(sibling=_safe_segment, extra=_safe_segment, content=_safe_content)
    @settings(max_examples=100)
    def test_absolute_path_outside_rejected_with_security_error(
        self, sibling: str, extra: str, content: str
    ) -> None:
        """Absolute paths outside the project boundary are rejected by save_file."""
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

            mock_settings = ChatSettings(
                project_path=project_root,
            )

            service = EditorService(project_dir=project_root, settings=mock_settings)

            # Run save_file - should reject without modifying anything
            result: SaveResult = asyncio.run(
                service.save_file(path_str, content)
            )

            # Verify: save rejected with security error
            assert result.success is False
            assert any("security" in err.lower() or "Security" in err for err in result.errors)

            # Verify: no files were created at the outside path
            assert not outside_path.exists(), (
                f"File was created outside project boundary at {outside_path}"
            )

    @given(
        escape_path=path_outside_via_dotdot(),
        original_content=_safe_content,
        new_content=_safe_content,
    )
    @settings(max_examples=100)
    def test_existing_files_unchanged_after_rejected_save(
        self, escape_path: str, original_content: str, new_content: str
    ) -> None:
        """When save is rejected, no existing files in the project are modified."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()

            # Verify the path actually resolves outside
            target = (project_root / escape_path).resolve()
            canonical_root = project_root.resolve()
            try:
                target.relative_to(canonical_root)
                assume(False)
            except ValueError:
                pass

            # Create an existing file inside the project to verify it's untouched
            existing_file = project_root / "existing.tjp"
            existing_file.write_text(original_content, encoding="utf-8")

            mock_settings = ChatSettings(
                project_path=project_root,
            )

            service = EditorService(project_dir=project_root, settings=mock_settings)

            # Run save_file with path outside boundary
            result: SaveResult = asyncio.run(
                service.save_file(escape_path, new_content)
            )

            # Verify: save rejected
            assert result.success is False

            # Verify: existing file content unchanged
            assert existing_file.read_text(encoding="utf-8") == original_content

            # Verify: no backup files created
            backup_files = list(project_root.glob("*.bak"))
            assert len(backup_files) == 0, (
                f"Backup files created during rejected save: {backup_files}"
            )
