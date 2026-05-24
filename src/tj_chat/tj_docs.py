"""TJ Documentation Service for loading and searching bundled TaskJuggler reference docs.

Provides search functionality and condensed syntax reference for inclusion
in the LLM system prompt.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from tj_chat.models import DocSection

logger = logging.getLogger(__name__)

# Key constructs to include in the condensed syntax reference
_KEY_CONSTRUCTS = ("task", "resource", "account", "report", "timesheet", "journalentry", "macro")


class TJDocumentationService:
    """Loads bundled TJ reference docs and provides search and syntax reference.

    If the docs path is missing or unreadable, operates in degraded mode where
    search returns empty results and syntax reference returns an empty string.
    """

    def __init__(self, docs_path: Path) -> None:
        """Load documentation from configured path.

        If docs_path is missing or unreadable, logs a warning and operates
        in degraded mode (search returns empty, syntax reference returns empty string).
        """
        self._sections: list[_LoadedSection] = []
        self._available: bool = False

        if not docs_path.exists():
            logger.warning("TJ docs path does not exist: %s", docs_path)
            return

        if not docs_path.is_dir():
            logger.warning("TJ docs path is not a directory: %s", docs_path)
            return

        try:
            self._load_docs(docs_path)
        except OSError as e:
            logger.warning("Failed to read TJ docs from %s: %s", docs_path, e)
            return

        if self._sections:
            self._available = True
        else:
            logger.warning("No documentation sections loaded from %s", docs_path)

    def search(self, query: str) -> list[DocSection]:
        """Search documentation for sections matching query terms.

        Splits query into terms, performs case-insensitive matching against
        section titles and content, and returns results ordered by relevance score.
        """
        if not self._available or not query.strip():
            return []

        terms = _split_query_terms(query)
        if not terms:
            return []

        results: list[DocSection] = []
        for section in self._sections:
            score = _compute_relevance(terms, section.title, section.content)
            if score > 0.0:
                results.append(
                    DocSection(
                        title=section.title,
                        content=section.content,
                        relevance_score=score,
                    )
                )

        results.sort(key=lambda s: s.relevance_score, reverse=True)
        return results

    def get_syntax_reference(self) -> str:
        """Return condensed key syntax sections for inclusion in system prompt.

        Covers: task, resource, account, report, timesheet, journalentry,
        and macro definitions. Returns empty string if docs unavailable.
        """
        if not self._available:
            return ""

        parts: list[str] = []
        for construct in _KEY_CONSTRUCTS:
            section = self._find_section(construct)
            if section is not None:
                condensed = _condense_section(section)
                if condensed:
                    parts.append(condensed)

        if not parts:
            return ""

        return "# TaskJuggler Syntax Reference\n\n" + "\n\n".join(parts)

    @property
    def is_available(self) -> bool:
        """Whether documentation was successfully loaded."""
        return self._available

    def _load_docs(self, docs_path: Path) -> None:
        """Load all markdown files from the docs directory."""
        for md_file in sorted(docs_path.glob("*.md")):
            try:
                content = md_file.read_text(encoding="utf-8")
            except OSError as e:
                logger.warning("Failed to read doc file %s: %s", md_file, e)
                continue

            title = _extract_title(content, md_file.stem)
            self._sections.append(_LoadedSection(title=title, content=content))

    def _find_section(self, construct: str) -> _LoadedSection | None:
        """Find a loaded section by construct name (case-insensitive title match)."""
        construct_lower = construct.lower()
        for section in self._sections:
            if section.title.lower() == construct_lower:
                return section
        return None


class _LoadedSection:
    """Internal representation of a loaded documentation section."""

    __slots__ = ("title", "content")

    def __init__(self, title: str, content: str) -> None:
        self.title = title
        self.content = content


def _extract_title(content: str, fallback: str) -> str:
    """Extract the title from the first H1 heading, or use the fallback."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


def _split_query_terms(query: str) -> list[str]:
    """Split a query string into lowercase search terms."""
    return [term.lower() for term in re.split(r"\s+", query.strip()) if term]


def _compute_relevance(terms: list[str], title: str, content: str) -> float:
    """Compute relevance score as fraction of query terms found in title or content.

    Title matches are weighted slightly higher than content-only matches to
    ensure sections whose title directly matches rank above sections that
    merely mention the term in their body.

    Score is clamped to [0.0, 1.0].
    """
    if not terms:
        return 0.0

    title_lower = title.lower()
    content_lower = content.lower()
    total_weight = 0.0

    for term in terms:
        if term in title_lower:
            # Title match gets full weight
            total_weight += 1.0
        elif term in content_lower:
            # Content-only match gets slightly less weight
            total_weight += 0.8

    score = total_weight / len(terms)
    return min(score, 1.0)


def _condense_section(section: _LoadedSection) -> str:
    """Extract the syntax block and key attributes from a documentation section.

    Returns a condensed version suitable for system prompt inclusion.
    """
    lines = section.content.splitlines()
    parts: list[str] = []
    parts.append(f"## {section.title}")

    # Extract the first code block (syntax definition)
    in_code_block = False
    code_block_lines: list[str] = []
    found_syntax_block = False

    for line in lines:
        if line.strip().startswith("```") and not in_code_block:
            in_code_block = True
            code_block_lines = [line]
            continue
        elif line.strip().startswith("```") and in_code_block:
            code_block_lines.append(line)
            if not found_syntax_block:
                parts.append("\n".join(code_block_lines))
                found_syntax_block = True
            in_code_block = False
            code_block_lines = []
            continue

        if in_code_block:
            code_block_lines.append(line)

    # Extract the first attributes table if present
    table_lines = _extract_first_table(lines)
    if table_lines:
        parts.append("\n".join(table_lines))

    return "\n\n".join(parts) if len(parts) > 1 else ""


def _extract_first_table(lines: list[str]) -> list[str]:
    """Extract the first markdown table from the lines."""
    table: list[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            table.append(line)
        elif in_table:
            # End of table
            break

    return table if len(table) >= 3 else []  # Header + separator + at least one row
