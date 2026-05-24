"""Pydantic data models for the Project File Editor.

Defines structured data types for the file tree browser, code editor,
save workflow, helper panel, and diff-based suggestion system.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


def classify_file_type(filename: str) -> Literal["tjp", "tji", "other"]:
    """Classify a filename by its extension.

    Args:
        filename: The file name (or path) to classify.

    Returns:
        "tjp" for .tjp files, "tji" for .tji files, "other" for everything else.
    """
    if filename.endswith(".tjp"):
        return "tjp"
    if filename.endswith(".tji"):
        return "tji"
    return "other"


def truncate_path_display(path: str, max_length: int = 60) -> str:
    """Truncate a file path for display in the editor header.

    If the path exceeds max_length characters, it is truncated with a
    leading ellipsis ("…") so that the filename portion is preserved at
    the end. If the path is max_length or fewer characters, it is
    returned unchanged.

    Args:
        path: The file path string to truncate.
        max_length: Maximum allowed length (default 60).

    Returns:
        The original path if within max_length, otherwise a truncated
        version starting with "…" and ending with the filename.
    """
    if len(path) <= max_length:
        return path

    # Extract the filename (last component after the last separator)
    # Handle both forward and backslash separators
    sep_idx = max(path.rfind("/"), path.rfind("\\"))
    if sep_idx == -1:
        # No separator found — the whole string is the filename
        filename = path
    else:
        filename = path[sep_idx + 1 :]

    # If the filename alone (plus ellipsis) exceeds max_length,
    # truncate the filename itself with ellipsis prefix
    if len(filename) + 1 >= max_length:
        return "…" + filename[-(max_length - 1) :]

    # Otherwise, take as much of the path suffix as fits
    # "…" takes 1 character, remaining budget is for the path suffix
    budget = max_length - 1  # 1 char for "…"
    return "…" + path[-budget:]


class FileNode(BaseModel):
    """Hierarchical file tree node for the sidebar browser."""

    name: str
    path: str  # Relative to project root
    is_directory: bool
    children: list[FileNode] = Field(default_factory=list)
    file_type: Literal["tjp", "tji", "other"] = "other"


class FileContent(BaseModel):
    """Result of reading a project file."""

    path: str
    content: str
    success: bool
    error: str | None = None


class SaveResult(BaseModel):
    """Result of a compiler-validated save operation."""

    success: bool
    errors: list[str] = Field(default_factory=list)
    backup_path: str | None = None


class EditorContext(BaseModel):
    """Context payload sent with helper panel messages to the LLM."""

    file_path: str | None = None
    file_content: str | None = None
    cursor_line: int = 0
    surrounding_lines: str = ""  # 10 lines above/below cursor
    project_files: list[str] = Field(default_factory=list)


class DiffSuggestion(BaseModel):
    """A diff-based code suggestion from the helper panel."""

    file_path: str
    start_line: int
    end_line: int
    original_content: str
    suggested_content: str
    status: Literal["pending", "accepted", "rejected", "outdated"] = "pending"


class HelperResponse(BaseModel):
    """Response from the helper service including optional diff suggestions."""

    text: str
    suggestions: list[DiffSuggestion] = Field(default_factory=list)
    error: str | None = None


def apply_suggestion(content: str, suggestion: DiffSuggestion) -> tuple[str, bool]:
    """Apply a diff suggestion to file content by replacing lines at the referenced range.

    Lines are 1-indexed: start_line=1 means the first line of the file.
    The function replaces lines from start_line to end_line (inclusive) with
    the suggested content, but only if the current content at that range
    matches the suggestion's original_content.

    This function does NOT mutate the suggestion object. The caller is
    responsible for updating the suggestion status.

    Args:
        content: The current file content as a string.
        suggestion: The DiffSuggestion to apply.

    Returns:
        A tuple of (new_content, success). If success is True, new_content
        contains the modified file. If False, the content is returned
        unchanged (conflict detected — suggestion is outdated).
    """
    lines = content.split("\n")

    # Convert 1-indexed to 0-indexed
    start_idx = suggestion.start_line - 1
    end_idx = suggestion.end_line  # end_line is inclusive, so slice up to end_idx

    # Extract the lines at the referenced range
    extracted_lines = lines[start_idx:end_idx]
    extracted_content = "\n".join(extracted_lines)

    # Conflict detection: compare extracted content with original_content
    if extracted_content != suggestion.original_content:
        return (content, False)

    # Replace the lines at the range with suggested content
    suggested_lines = suggestion.suggested_content.split("\n")
    new_lines = lines[:start_idx] + suggested_lines + lines[end_idx:]
    new_content = "\n".join(new_lines)

    return (new_content, True)
