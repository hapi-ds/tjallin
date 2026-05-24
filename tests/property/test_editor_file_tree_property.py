"""Property-based tests for the editor file tree.

# Feature: project-file-editor, Property 3: File tree path boundary

**Validates: Requirements 2.6, 8.1, 8.4**

For any file node in the built file tree, resolving its path SHALL produce
a canonical path that is within or equal to the project root directory.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.editor_service import EditorService
from tj_chat.editor_models import FileNode
from tj_chat.settings import ChatSettings

# Windows reserved device names that cannot be used as file/directory names
_WINDOWS_RESERVED = frozenset({
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
})

# Strategy for valid directory/file name characters (letters only to avoid issues)
_name_char = st.characters(
    categories=("L",),
    exclude_characters="\x00/\\:.",
)

# Strategy for a safe file/directory name (non-hidden, no reserved names on Windows)
_safe_name = st.text(alphabet=_name_char, min_size=2, max_size=12).filter(
    lambda s: s.strip() != ""
    and not s.startswith(".")
    and s.upper() not in _WINDOWS_RESERVED
)

# Strategy for file extensions
_extension = st.sampled_from([".tjp", ".tji", ".txt", ".md", ".py"])


@st.composite
def directory_structure(draw: st.DrawFn) -> list[str]:
    """Generate a list of relative file paths to create in a temp directory.

    Creates a mix of files in subdirectories (1-3 levels deep).
    Avoids conflicts where a name is used as both a file and a directory.
    """
    num_entries = draw(st.integers(min_value=1, max_value=8))
    paths: list[str] = []
    # Track which names are used as directories to avoid file/dir conflicts
    used_as_dir: set[str] = set()
    used_as_file: set[str] = set()

    for _ in range(num_entries):
        depth = draw(st.integers(min_value=1, max_value=3))
        segments = [draw(_safe_name) for _ in range(depth)]
        ext = draw(_extension)
        # Last segment is the file name
        segments[-1] = segments[-1] + ext

        # Check for conflicts: intermediate segments become directories
        conflict = False
        for i, seg in enumerate(segments[:-1]):
            prefix = "/".join(segments[: i + 1])
            if prefix in used_as_file:
                conflict = True
                break
            used_as_dir.add(prefix)

        # The full path is a file
        full = "/".join(segments)
        if full in used_as_dir:
            conflict = True

        if not conflict:
            used_as_file.add(full)
            paths.append(full)

    # Ensure at least one path
    if not paths:
        name = draw(_safe_name)
        ext = draw(_extension)
        paths.append(name + ext)

    return paths


def collect_all_nodes(nodes: list[FileNode]) -> list[FileNode]:
    """Recursively collect all FileNode instances from the tree."""
    result: list[FileNode] = []
    for node in nodes:
        result.append(node)
        if node.children:
            result.extend(collect_all_nodes(node.children))
    return result


class TestFileTreePathBoundary:
    """Property 3: File tree path boundary.

    **Validates: Requirements 2.6, 8.1, 8.4**
    """

    @given(file_paths=directory_structure())
    @settings(max_examples=100)
    def test_all_nodes_resolve_within_project_root(
        self, file_paths: list[str]
    ) -> None:
        """For any file node in the tree, its resolved path is within or equal to the project root."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()

            # Create the generated directory structure
            for rel_path in file_paths:
                full_path = project_root / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                if not full_path.exists():
                    full_path.touch()

            # Build the file tree using EditorService
            chat_settings = ChatSettings(project_path=project_root)
            service = EditorService(
                project_dir=project_root, settings=chat_settings
            )
            tree = service.build_file_tree()

            # Collect all nodes recursively
            all_nodes = collect_all_nodes(tree)

            # Verify every node's path resolves within the project root
            canonical_root = project_root.resolve()
            for node in all_nodes:
                resolved = (canonical_root / node.path).resolve()
                # The resolved path must be within or equal to the project root
                resolved.relative_to(canonical_root)  # Raises ValueError if outside

    @given(file_paths=directory_structure())
    @settings(max_examples=100)
    def test_nodes_with_subdirectories_stay_within_boundary(
        self, file_paths: list[str]
    ) -> None:
        """Subdirectory nodes also have paths that resolve within the project root."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()

            # Create the generated directory structure
            for rel_path in file_paths:
                full_path = project_root / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                if not full_path.exists():
                    full_path.touch()

            # Build the file tree
            chat_settings = ChatSettings(project_path=project_root)
            service = EditorService(
                project_dir=project_root, settings=chat_settings
            )
            tree = service.build_file_tree()

            # Collect only directory nodes
            all_nodes = collect_all_nodes(tree)
            dir_nodes = [n for n in all_nodes if n.is_directory]

            canonical_root = project_root.resolve()
            for node in dir_nodes:
                resolved = (canonical_root / node.path).resolve()
                resolved.relative_to(canonical_root)  # Raises ValueError if outside

    @given(file_paths=directory_structure())
    @settings(max_examples=100)
    def test_node_paths_are_relative_to_project_root(
        self, file_paths: list[str]
    ) -> None:
        """All node paths are relative (not absolute) and resolve correctly from project root."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_root = Path(tmp_dir) / "project"
            project_root.mkdir()

            # Create the generated directory structure
            for rel_path in file_paths:
                full_path = project_root / rel_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                if not full_path.exists():
                    full_path.touch()

            # Build the file tree
            chat_settings = ChatSettings(project_path=project_root)
            service = EditorService(
                project_dir=project_root, settings=chat_settings
            )
            tree = service.build_file_tree()

            # Collect all nodes
            all_nodes = collect_all_nodes(tree)

            canonical_root = project_root.resolve()
            for node in all_nodes:
                # Path should be relative (not start with / or drive letter)
                assert not Path(node.path).is_absolute(), (
                    f"Node path should be relative, got: {node.path}"
                )
                # Resolving from project root should land within the boundary
                resolved = (canonical_root / node.path).resolve()
                resolved.relative_to(canonical_root)
