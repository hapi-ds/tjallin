"""Editor service for file operations within the project boundary.

Encapsulates file tree building, file read/write with validation,
and backup logic for the Project File Editor.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path

from tj_chat.editor_models import (
    FileContent,
    FileNode,
    SaveResult,
    classify_file_type,
)
from tj_chat.models import PathSecurityError
from tj_chat.path_safety import validate_project_path
from tj_chat.settings import ChatSettings

logger = logging.getLogger(__name__)


class EditorService:
    """Service encapsulating file operations for the editor.

    Provides file tree building, file reading, and compiler-validated
    save operations, all enforced through PathSafetyModule.

    Args:
        project_dir: The root directory of the project.
        settings: Application settings including project_path.
    """

    def __init__(self, project_dir: Path, settings: ChatSettings) -> None:
        self._project_dir = project_dir.resolve()
        self._settings = settings

    def build_file_tree(self) -> list[FileNode]:
        """Build a hierarchical file tree for the project directory.

        Enumerates all files and directories within the project root,
        excluding hidden entries (names starting with '.'), sorting
        directories first then files (both alphabetically, case-insensitive),
        classifying file types, and validating all paths through
        PathSafetyModule.

        Returns:
            A list of FileNode instances representing the top-level entries,
            with recursive children for subdirectories.
        """
        return self._build_tree(self._project_dir)

    async def read_file(self, relative_path: str) -> FileContent:
        """Read a file within the project boundary.

        Resolves the relative path against the project directory, validates
        it through PathSafetyModule, and reads the file content.

        Args:
            relative_path: Path relative to the project root.

        Returns:
            FileContent with the file content on success, or an error
            message on failure.
        """
        resolved = self._project_dir / relative_path

        try:
            validate_project_path(resolved, self._project_dir)
        except PathSecurityError as e:
            logger.warning("Path security violation reading %s: %s", relative_path, e)
            return FileContent(
                path=relative_path,
                content="",
                success=False,
                error="Security error: path is outside the project boundary",
            )

        try:
            content = resolved.resolve().read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Failed to read file %s: %s", relative_path, e)
            return FileContent(
                path=relative_path,
                content="",
                success=False,
                error=f"Failed to read file: {e}",
            )

        return FileContent(
            path=relative_path,
            content=content,
            success=True,
        )

    async def save_file(self, relative_path: str, content: str) -> SaveResult:
        """Save file with backup → write → compile → rollback-on-failure workflow.

        Validates the path, creates a backup, writes the new content,
        validates the project with tj3, and rolls back if compilation fails.

        Args:
            relative_path: Path relative to the project root.
            content: The new file content to save.

        Returns:
            SaveResult with success status, backup path on success,
            or error messages on failure.
        """
        # 1. Validate path through PathSafetyModule
        target_path = self._project_dir / relative_path
        try:
            resolved_target = validate_project_path(target_path, self._project_dir)
        except PathSecurityError:
            logger.warning(
                "Path security violation saving %s", relative_path
            )
            return SaveResult(
                success=False,
                errors=["Security error: path is outside the project boundary"],
            )

        # 2. Create backup of original file (if it exists)
        backup_path: str | None = None
        original_content: str | None = None
        if resolved_target.exists():
            original_content = resolved_target.read_text(encoding="utf-8")
            bak_path = resolved_target.with_suffix(
                resolved_target.suffix + ".bak"
            )
            try:
                shutil.copy2(resolved_target, bak_path)
                backup_path = str(bak_path.relative_to(self._project_dir))
            except OSError as e:
                logger.error(
                    "Failed to create backup for %s: %s", relative_path, e
                )
                return SaveResult(
                    success=False,
                    errors=[f"Backup creation failed: {e}"],
                )

        # 3. Write new content to the target file
        try:
            resolved_target.parent.mkdir(parents=True, exist_ok=True)
            resolved_target.write_text(content, encoding="utf-8")
        except OSError as e:
            logger.error("Failed to write file %s: %s", relative_path, e)
            return SaveResult(
                success=False,
                errors=[f"Failed to write file: {e}"],
            )

        # 4. Validate by compiling the main project file with tj3
        try:
            process = await asyncio.create_subprocess_exec(
                "tj3",
                "--check-syntax",
                self._settings.project_file,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self._project_dir),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=30.0
            )
            compiler_success = process.returncode == 0
            compiler_stderr = stderr_bytes.decode("utf-8", errors="replace")
        except FileNotFoundError:
            # tj3 not found — rollback and report
            if original_content is not None:
                resolved_target.write_text(original_content, encoding="utf-8")
            return SaveResult(
                success=False,
                errors=[
                    "tj3 compiler not found. Ensure TaskJuggler is installed."
                ],
            )
        except asyncio.TimeoutError:
            process.kill()  # type: ignore[union-attr]
            await process.wait()  # type: ignore[union-attr]
            if original_content is not None:
                resolved_target.write_text(original_content, encoding="utf-8")
            return SaveResult(
                success=False,
                errors=["Compiler validation timed out after 30 seconds."],
            )

        # 5. Handle compiler result
        if not compiler_success:
            # Rollback: restore original content
            if original_content is not None:
                resolved_target.write_text(original_content, encoding="utf-8")
            else:
                resolved_target.unlink(missing_ok=True)
            errors = [
                line
                for line in compiler_stderr.strip().splitlines()
                if line.strip()
            ]
            if not errors:
                errors = ["Compilation failed with unknown error."]
            return SaveResult(success=False, errors=errors)

        # 6. Success — file is already written, backup exists
        return SaveResult(
            success=True,
            backup_path=backup_path,
        )

    def _build_tree(self, directory: Path, _depth: int = 0) -> list[FileNode]:
        """Recursively build file tree nodes for a directory.

        Args:
            directory: The directory to enumerate.
            _depth: Current recursion depth (guards against symlink loops).

        Returns:
            Sorted list of FileNode instances for the directory contents.
        """
        # Guard against symlink loops or excessively deep trees
        if _depth > 20:
            logger.warning("Max depth reached at %s, stopping recursion", directory)
            return []

        nodes: list[FileNode] = []

        try:
            entries = list(directory.iterdir())
        except OSError as e:
            logger.warning("Cannot read directory %s: %s", directory, e)
            return nodes

        for entry in entries:
            # Exclude hidden entries (names starting with '.')
            if entry.name.startswith("."):
                continue

            # Skip symlinks to avoid infinite loops
            if entry.is_symlink():
                continue

            # Validate path through PathSafetyModule
            try:
                validate_project_path(entry, self._project_dir)
            except PathSecurityError:
                logger.warning(
                    "Skipping path outside project boundary: %s", entry
                )
                continue

            # Compute relative path from project root
            relative_path = str(entry.relative_to(self._project_dir))

            if entry.is_dir():
                children = self._build_tree(entry, _depth + 1)
                node = FileNode(
                    name=entry.name,
                    path=relative_path,
                    is_directory=True,
                    children=children,
                    file_type="other",
                )
            else:
                node = FileNode(
                    name=entry.name,
                    path=relative_path,
                    is_directory=False,
                    file_type=classify_file_type(entry.name),
                )

            nodes.append(node)

        # Sort: directories first, then files, both alphabetically (case-insensitive)
        nodes.sort(key=lambda n: (not n.is_directory, n.name.lower()))

        return nodes
