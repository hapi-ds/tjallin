"""Property-based tests for task similarity search.

**Validates: Requirements 4.5, 5.6**

Property 10: Task similarity search returns bounded ordered results.
- For any query string and list of existing task paths where the query does not
  exactly match any path, the similarity search SHALL return at most 5 results
  ordered by decreasing similarity score.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.project_reader import ProjectReader

# Strategy for task IDs: valid TaskJuggler identifiers (alphanumeric + underscores)
_task_id = st.text(
    alphabet=st.characters(categories=("L", "N"), include_characters="_"),
    min_size=1,
    max_size=20,
).filter(lambda s: s[0].isalpha())

# Strategy for task names: printable text without quotes (valid TJ task names)
_task_name = st.text(
    alphabet=st.characters(
        categories=("L", "N", "Z"),
        include_characters="-_ ",
    ),
    min_size=1,
    max_size=40,
).filter(lambda s: '"' not in s and s.strip() == s and len(s.strip()) > 0)

# Strategy for a list of tasks (1 to 15 tasks)
_task_list = st.lists(
    st.tuples(_task_id, _task_name),
    min_size=1,
    max_size=15,
    unique_by=lambda t: t[0],  # Unique task IDs
)

# Strategy for query strings: non-empty text that won't exactly match a task path
_query = st.text(
    alphabet=st.characters(categories=("L", "N"), include_characters="-_. "),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip() != "")


def _create_tasks_file(tasks: list[tuple[str, str]]) -> str:
    """Generate a valid TaskJuggler .tji file content with task definitions.

    Args:
        tasks: List of (task_id, task_name) tuples.

    Returns:
        String content for a .tji file.
    """
    lines: list[str] = []
    for task_id, task_name in tasks:
        lines.append(f'task {task_id} "{task_name}" {{')
        lines.append("  effort 1d")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


class TestTaskSimilaritySearchProperty:
    """Property 10: Task similarity search returns bounded ordered results.

    **Validates: Requirements 4.5, 5.6**
    """

    @given(tasks=_task_list, query=_query)
    @settings(max_examples=100)
    def test_results_at_most_five(
        self, tasks: list[tuple[str, str]], query: str
    ) -> None:
        """Similarity search returns at most 5 results."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            tasks_file = project_dir / "tasks.tji"
            tasks_file.write_text(_create_tasks_file(tasks), encoding="utf-8")

            reader = ProjectReader(project_dir)
            results = reader.find_task(query)

            assert len(results) <= 5, (
                f"Expected at most 5 results, got {len(results)} "
                f"for query {query!r} with {len(tasks)} tasks"
            )

    @given(tasks=_task_list, query=_query)
    @settings(max_examples=100)
    def test_results_ordered_by_decreasing_score(
        self, tasks: list[tuple[str, str]], query: str
    ) -> None:
        """Results are ordered by decreasing similarity score."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            tasks_file = project_dir / "tasks.tji"
            tasks_file.write_text(_create_tasks_file(tasks), encoding="utf-8")

            reader = ProjectReader(project_dir)
            results = reader.find_task(query)

            if len(results) > 1:
                scores = [r.score for r in results]
                for i in range(len(scores) - 1):
                    assert scores[i] >= scores[i + 1], (
                        f"Results not in decreasing order: "
                        f"score[{i}]={scores[i]} < score[{i + 1}]={scores[i + 1]} "
                        f"for query {query!r}"
                    )

    @given(tasks=_task_list, query=_query)
    @settings(max_examples=100)
    def test_all_scores_between_zero_and_one(
        self, tasks: list[tuple[str, str]], query: str
    ) -> None:
        """All similarity scores are between 0 and 1 (inclusive)."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            project_dir = Path(tmp_dir)
            tasks_file = project_dir / "tasks.tji"
            tasks_file.write_text(_create_tasks_file(tasks), encoding="utf-8")

            reader = ProjectReader(project_dir)
            results = reader.find_task(query)

            for match in results:
                assert 0.0 <= match.score <= 1.0, (
                    f"Score {match.score} out of range [0, 1] "
                    f"for task {match.task.path!r} with query {query!r}"
                )
