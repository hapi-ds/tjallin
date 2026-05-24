"""Property-based tests for TJ Documentation Service search.

**Validates: Requirements 13.5**

Property 19: TJ docs search returns relevant sections matching query terms.
- For any non-empty query string and a loaded documentation corpus, the
  search_tj_docs tool SHALL return only DocSection results whose title or
  content contains at least one term from the query (case-insensitive),
  and results SHALL be ordered by decreasing relevance score.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.tj_docs import TJDocumentationService

# Strategy for documentation section titles (simple identifiers)
_doc_title = st.text(
    alphabet=st.characters(categories=("L",), include_characters="_"),
    min_size=2,
    max_size=15,
).filter(lambda s: s.strip() != "" and s[0].isalpha())

# Strategy for documentation content (printable text with some substance)
_doc_content = st.text(
    alphabet=st.characters(categories=("L", "N", "Z"), include_characters=".-_,;:"),
    min_size=10,
    max_size=200,
).filter(lambda s: len(s.strip()) >= 5)

# Strategy for a single documentation file (title + content)
_doc_file = st.tuples(_doc_title, _doc_content)

# Strategy for a corpus of documentation files (1 to 8 files)
_doc_corpus = st.lists(
    _doc_file,
    min_size=1,
    max_size=8,
    unique_by=lambda t: t[0].lower(),
)

# Strategy for query terms: words that could appear in titles or content
_query_term = st.text(
    alphabet=st.characters(categories=("L", "N"), include_characters="_"),
    min_size=2,
    max_size=12,
).filter(lambda s: s.strip() != "")

# Strategy for multi-term queries (1 to 3 terms separated by spaces)
_query = st.lists(_query_term, min_size=1, max_size=3).map(" ".join)


def _create_docs_directory(
    docs: list[tuple[str, str]], base_dir: Path
) -> Path:
    """Create a temporary docs directory with markdown files.

    Args:
        docs: List of (title, content) tuples.
        base_dir: Parent directory to create docs folder in.

    Returns:
        Path to the created docs directory.
    """
    docs_dir = base_dir / "tj-docs"
    docs_dir.mkdir(exist_ok=True)

    for title, content in docs:
        filename = title.lower().replace(" ", "_") + ".md"
        file_content = f"# {title}\n\n{content}\n"
        (docs_dir / filename).write_text(file_content, encoding="utf-8")

    return docs_dir


class TestTJDocsSearchProperty:
    """Property 19: TJ docs search returns relevant sections matching query terms.

    **Validates: Requirements 13.5**
    """

    @given(docs=_doc_corpus, query=_query)
    @settings(max_examples=100)
    def test_all_results_contain_at_least_one_query_term(
        self, docs: list[tuple[str, str]], query: str
    ) -> None:
        """All returned results contain at least one query term in title or content."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = _create_docs_directory(docs, Path(tmp_dir))
            service = TJDocumentationService(docs_dir)

            results = service.search(query)
            terms = [t.lower() for t in query.split() if t.strip()]

            for section in results:
                title_lower = section.title.lower()
                content_lower = section.content.lower()
                has_match = any(
                    term in title_lower or term in content_lower
                    for term in terms
                )
                assert has_match, (
                    f"Result '{section.title}' does not contain any query term "
                    f"from {terms!r} in title or content"
                )

    @given(docs=_doc_corpus, query=_query)
    @settings(max_examples=100)
    def test_results_ordered_by_decreasing_relevance_score(
        self, docs: list[tuple[str, str]], query: str
    ) -> None:
        """Results are ordered by decreasing relevance_score."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = _create_docs_directory(docs, Path(tmp_dir))
            service = TJDocumentationService(docs_dir)

            results = service.search(query)

            if len(results) > 1:
                scores = [r.relevance_score for r in results]
                for i in range(len(scores) - 1):
                    assert scores[i] >= scores[i + 1], (
                        f"Results not in decreasing order: "
                        f"score[{i}]={scores[i]} < score[{i + 1}]={scores[i + 1]} "
                        f"for query {query!r}"
                    )

    @given(docs=_doc_corpus, query=_query)
    @settings(max_examples=100)
    def test_all_relevance_scores_between_zero_and_one(
        self, docs: list[tuple[str, str]], query: str
    ) -> None:
        """All relevance_scores are between 0.0 and 1.0 (inclusive)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            docs_dir = _create_docs_directory(docs, Path(tmp_dir))
            service = TJDocumentationService(docs_dir)

            results = service.search(query)

            for section in results:
                assert 0.0 <= section.relevance_score <= 1.0, (
                    f"Relevance score {section.relevance_score} out of range [0, 1] "
                    f"for section '{section.title}' with query {query!r}"
                )
