"""Property-based tests for file type classification.

# Feature: project-file-editor, Property 2: File type classification

**Validates: Requirements 2.2**

For any file name, the file type classifier SHALL return "tjp" if the
extension is `.tjp`, "tji" if the extension is `.tji`, and "other" for
all other extensions (including no extension).
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.editor_models import classify_file_type

# Strategy for valid filename characters (no null bytes, no path separators)
_filename_char = st.characters(
    categories=("L", "N", "P"),
    exclude_characters="\x00/\\:",
)

# Strategy for a base filename (without extension)
_base_name = st.text(alphabet=_filename_char, min_size=1, max_size=30).filter(
    lambda s: s.strip() != "" and not s.endswith(".")
)

# Strategy for arbitrary extensions that are NOT .tjp or .tji
_other_extension = st.text(alphabet=_filename_char, min_size=1, max_size=10).filter(
    lambda s: s.strip() != ""
    and not s.endswith("tjp")
    and not s.endswith("tji")
)


class TestFileTypeClassification:
    """Property 2: File type classification.

    **Validates: Requirements 2.2**
    """

    @given(base=_base_name)
    @settings(max_examples=100)
    def test_tjp_extension_returns_tjp(self, base: str) -> None:
        """Any filename ending with .tjp is classified as 'tjp'."""
        filename = f"{base}.tjp"
        assert classify_file_type(filename) == "tjp"

    @given(base=_base_name)
    @settings(max_examples=100)
    def test_tji_extension_returns_tji(self, base: str) -> None:
        """Any filename ending with .tji is classified as 'tji'."""
        filename = f"{base}.tji"
        assert classify_file_type(filename) == "tji"

    @given(base=_base_name, ext=_other_extension)
    @settings(max_examples=100)
    def test_other_extension_returns_other(self, base: str, ext: str) -> None:
        """Any filename with an extension other than .tjp/.tji is classified as 'other'."""
        filename = f"{base}.{ext}"
        assert classify_file_type(filename) == "other"

    @given(base=_base_name)
    @settings(max_examples=100)
    def test_no_extension_returns_other(self, base: str) -> None:
        """Any filename without an extension is classified as 'other'."""
        # Ensure no dot in the base name to guarantee no extension
        filename = base.replace(".", "")
        if not filename:
            filename = "file"
        assert classify_file_type(filename) == "other"

    @given(base=_base_name, path_prefix=_base_name)
    @settings(max_examples=100)
    def test_tjp_with_path_prefix_returns_tjp(
        self, base: str, path_prefix: str
    ) -> None:
        """File paths ending with .tjp are classified as 'tjp' regardless of directory prefix."""
        filename = f"{path_prefix}/{base}.tjp"
        assert classify_file_type(filename) == "tjp"

    @given(base=_base_name, path_prefix=_base_name)
    @settings(max_examples=100)
    def test_tji_with_path_prefix_returns_tji(
        self, base: str, path_prefix: str
    ) -> None:
        """File paths ending with .tji are classified as 'tji' regardless of directory prefix."""
        filename = f"{path_prefix}/{base}.tji"
        assert classify_file_type(filename) == "tji"
