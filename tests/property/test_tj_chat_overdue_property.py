"""Property-based tests for overdue task detection.

**Validates: Requirements 8.4, 8.5**

Property 14: Overdue detection uses configured project date.
- For any task with a planned end date before the project's configured now date
  and without 100% completion, the overdue detection SHALL flag that task as
  overdue and report the correct number of days between the planned end date
  and the configured now date.
"""

from __future__ import annotations

from datetime import date, timedelta

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tj_chat.models import TaskInfo
from tj_chat.overdue import detect_overdue_tasks

# --- Strategies ---

# Strategy for dates in a reasonable range
_date = st.dates(min_value=date(2000, 1, 1), max_value=date(2099, 12, 31))

# Strategy for completion percentage (0-99 means incomplete, 100 means complete)
_incomplete_percent = st.integers(min_value=0, max_value=99)
_complete_percent = st.just(100)

# Strategy for task path identifiers
_task_path = st.from_regex(r"[a-z][a-z0-9_.]{2,30}", fullmatch=True)

# Strategy for task names
_task_name = st.text(
    alphabet=st.characters(categories=("L", "N", "Z")),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip() != "")


def _build_task(
    path: str,
    name: str,
    end_date: date | None,
    complete: int | None,
) -> TaskInfo:
    """Helper to build a TaskInfo with the given attributes."""
    return TaskInfo(
        path=path,
        name=name,
        end_date=end_date.isoformat() if end_date is not None else None,
        complete=complete,
    )


class TestOverdueDetectionProperty:
    """Property 14: Overdue detection uses configured project date.

    **Validates: Requirements 8.4, 8.5**
    """

    @given(
        task_path=_task_path,
        task_name=_task_name,
        end_date=_date,
        now_date=_date,
        complete=_incomplete_percent,
    )
    @settings(max_examples=200)
    def test_task_before_now_and_incomplete_is_flagged_overdue(
        self,
        task_path: str,
        task_name: str,
        end_date: date,
        now_date: date,
        complete: int,
    ) -> None:
        """Tasks with end_date before now_date and complete != 100 are always flagged."""
        assume(end_date < now_date)

        task = _build_task(task_path, task_name, end_date, complete)
        result = detect_overdue_tasks([task], now_date)

        assert len(result) == 1, (
            f"Expected 1 overdue task, got {len(result)}. "
            f"end_date={end_date}, now_date={now_date}, complete={complete}"
        )
        assert result[0].task.path == task_path

    @given(
        task_path=_task_path,
        task_name=_task_name,
        end_date=_date,
        now_date=_date,
        complete=_incomplete_percent,
    )
    @settings(max_examples=200)
    def test_days_overdue_is_exactly_date_difference(
        self,
        task_path: str,
        task_name: str,
        end_date: date,
        now_date: date,
        complete: int,
    ) -> None:
        """The days_overdue is exactly (now_date - end_date).days."""
        assume(end_date < now_date)

        task = _build_task(task_path, task_name, end_date, complete)
        result = detect_overdue_tasks([task], now_date)

        expected_days = (now_date - end_date).days
        assert result[0].days_overdue == expected_days, (
            f"Expected {expected_days} days overdue, got {result[0].days_overdue}. "
            f"end_date={end_date}, now_date={now_date}"
        )

    @given(
        task_path=_task_path,
        task_name=_task_name,
        end_date=_date,
        now_date=_date,
    )
    @settings(max_examples=200)
    def test_completed_task_is_never_flagged(
        self,
        task_path: str,
        task_name: str,
        end_date: date,
        now_date: date,
    ) -> None:
        """Tasks with complete == 100 are never flagged as overdue."""
        assume(end_date < now_date)

        task = _build_task(task_path, task_name, end_date, 100)
        result = detect_overdue_tasks([task], now_date)

        assert len(result) == 0, (
            f"Completed task should not be flagged overdue. "
            f"end_date={end_date}, now_date={now_date}"
        )

    @given(
        task_path=_task_path,
        task_name=_task_name,
        end_date=_date,
        now_date=_date,
        complete=_incomplete_percent,
    )
    @settings(max_examples=200)
    def test_task_on_or_after_now_is_never_flagged(
        self,
        task_path: str,
        task_name: str,
        end_date: date,
        now_date: date,
        complete: int,
    ) -> None:
        """Tasks with end_date >= now_date are never flagged as overdue."""
        assume(end_date >= now_date)

        task = _build_task(task_path, task_name, end_date, complete)
        result = detect_overdue_tasks([task], now_date)

        assert len(result) == 0, (
            f"Task not yet due should not be flagged overdue. "
            f"end_date={end_date}, now_date={now_date}, complete={complete}"
        )
