"""Path safety module for restricting file operations to the project boundary.

Ensures all file paths are resolved to canonical absolute form and validated
against the configured project root directory before any file operation.
"""

from pathlib import Path

from tj_chat.models import PathSecurityError


def is_within_project(resolved_path: Path, project_root: Path) -> bool:
    """Check if resolved path is within or equal to project_root.

    Both paths should already be resolved to canonical absolute form
    before calling this function.

    Args:
        resolved_path: The canonical absolute path to check.
        project_root: The canonical absolute project root directory.

    Returns:
        True if resolved_path is equal to or a descendant of project_root.
    """
    try:
        resolved_path.relative_to(project_root)
        return True
    except ValueError:
        return False


def validate_project_path(path: str | Path, project_root: Path) -> Path:
    """Resolve path to canonical form and verify it's within project_root.

    Resolves the given path to its canonical absolute form (handling '..',
    '.', and symlinks) and checks that the result is within the project
    root directory.

    Args:
        path: The file path to validate (relative or absolute).
        project_root: The project root directory to validate against.

    Returns:
        The resolved canonical absolute path.

    Raises:
        PathSecurityError: If the resolved path is outside the project boundary.
    """
    # Resolve project_root to canonical form first
    canonical_root = project_root.resolve()

    # If path is relative, resolve it relative to the project root
    target = Path(path)
    if not target.is_absolute():
        target = canonical_root / target

    # Resolve to canonical absolute form (handles .., ., and symlinks)
    canonical_path = target.resolve()

    if not is_within_project(canonical_path, canonical_root):
        raise PathSecurityError(
            path=str(path),
            project_root=str(canonical_root),
        )

    return canonical_path
