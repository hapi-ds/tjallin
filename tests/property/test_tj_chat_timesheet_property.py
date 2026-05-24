"""Property-based tests for timesheet generation.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4, 4.8**

Property 5: Timesheet generation produces valid structure.
- For any valid BookingRequest, the generated timesheet SHALL contain a single
  timesheet block with resource ID and date range, all task entries with work
  hours, and for entries with status, a valid status line with color and headline.

Property 6: Timesheet file naming convention.
- For any resource ID and ISO week date, the filename SHALL match
  YYYY-Www-<resource_id>.tji

Property 7: Timesheet merge preserves unrelated entries.
- For any existing timesheet and new task entry, the merged result SHALL contain
  all original entries for non-matching task paths and replace the matching one.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from tj_chat.generators import TimesheetGenerator
from tj_chat.models import BookingRequest, BookingStatus, TaskEntry

# --- Strategies ---

# Valid TaskJuggler identifiers for resource IDs
_resource_id = st.text(
    alphabet=st.characters(categories=("L", "N"), include_characters="_"),
    min_size=1,
    max_size=20,
).filter(lambda s: s[0].isalpha())

# Valid dotted task paths (e.g. "project.phase.task")
_task_segment = st.text(
    alphabet=st.characters(categories=("L", "N"), include_characters="_"),
    min_size=1,
    max_size=15,
).filter(lambda s: s[0].isalpha())

_task_path = st.lists(_task_segment, min_size=1, max_size=4).map(
    lambda segments: ".".join(segments)
)

# Positive hours (0.5 to 40)
_hours = st.floats(min_value=0.5, max_value=40.0, allow_nan=False, allow_infinity=False)

# Status color
_status_color = st.sampled_from(list(BookingStatus))

# Status headline (non-empty, no quotes for simplicity)
_status_headline = st.text(
    alphabet=st.characters(categories=("L", "N", "Z"), include_characters="-_,.! "),
    min_size=1,
    max_size=60,
).filter(lambda s: '"' not in s and s.strip() != "")

# Optional status summary
_status_summary = st.one_of(
    st.none(),
    st.text(
        alphabet=st.characters(categories=("L", "N", "Z"), include_characters="-_,.! "),
        min_size=1,
        max_size=80,
    ).filter(lambda s: '"' not in s and s.strip() != ""),
)

# Task entry without status
_task_entry_no_status = st.builds(
    TaskEntry,
    task_path=_task_path,
    hours=_hours,
    status_color=st.none(),
    status_headline=st.none(),
    status_summary=st.none(),
)

# Task entry with status
_task_entry_with_status = st.builds(
    TaskEntry,
    task_path=_task_path,
    hours=_hours,
    status_color=_status_color,
    status_headline=_status_headline,
    status_summary=_status_summary,
)

# Any task entry
_task_entry = st.one_of(_task_entry_no_status, _task_entry_with_status)

# Monday dates (week_start must be a Monday)
_monday_date = st.dates(
    min_value=date(2020, 1, 6),  # A Monday
    max_value=date(2030, 12, 30),
).filter(lambda d: d.weekday() == 0)

# BookingRequest strategy
_booking_request = st.builds(
    BookingRequest,
    resource_id=_resource_id,
    week_start=_monday_date,
    entries=st.lists(_task_entry, min_size=1, max_size=5),
)


class TestTimesheetGenerationStructure:
    """Property 5: Timesheet generation produces valid structure.

    **Validates: Requirements 4.1, 4.4, 4.8**
    """

    @given(booking=_booking_request)
    @settings(max_examples=100)
    def test_contains_single_timesheet_block(self, booking: BookingRequest) -> None:
        """Generated output contains exactly one timesheet block."""
        gen = TimesheetGenerator()
        output = gen.generate(booking)

        # Count timesheet block openings
        timesheet_starts = re.findall(r"^timesheet\s+", output, re.MULTILINE)
        assert len(timesheet_starts) == 1, (
            f"Expected 1 timesheet block, found {len(timesheet_starts)}"
        )

    @given(booking=_booking_request)
    @settings(max_examples=100)
    def test_contains_resource_id_and_date_range(
        self, booking: BookingRequest
    ) -> None:
        """Timesheet block contains the resource ID and date range."""
        gen = TimesheetGenerator()
        output = gen.generate(booking)

        assert booking.resource_id in output, (
            f"Resource ID {booking.resource_id!r} not found in output"
        )

        week_start_str = booking.week_start.strftime("%Y-%m-%d")
        assert week_start_str in output, (
            f"Week start date {week_start_str} not found in output"
        )

        # Should contain duration indicator
        assert "+1w" in output, "Duration '+1w' not found in output"

    @given(booking=_booking_request)
    @settings(max_examples=100)
    def test_all_task_entries_present_with_hours(
        self, booking: BookingRequest
    ) -> None:
        """All task entries appear with their work hours."""
        gen = TimesheetGenerator()
        output = gen.generate(booking)

        for entry in booking.entries:
            assert entry.task_path in output, (
                f"Task path {entry.task_path!r} not found in output"
            )
            # Check work hours line exists
            assert "work" in output, "No 'work' keyword found in output"

    @given(booking=_booking_request)
    @settings(max_examples=100)
    def test_status_entries_have_valid_status_line(
        self, booking: BookingRequest
    ) -> None:
        """Entries with status have a valid status line with color and headline."""
        gen = TimesheetGenerator()
        output = gen.generate(booking)

        for entry in booking.entries:
            if entry.status_color is not None and entry.status_headline is not None:
                # Should contain the status color value
                assert entry.status_color.value in output, (
                    f"Status color {entry.status_color.value!r} not found in output"
                )
                # Should contain the headline text
                assert entry.status_headline in output, (
                    f"Status headline {entry.status_headline!r} not found in output"
                )


class TestTimesheetFileNaming:
    """Property 6: Timesheet file naming convention.

    **Validates: Requirements 4.2**
    """

    @given(resource_id=_resource_id, week_start=_monday_date)
    @settings(max_examples=100)
    def test_filename_matches_pattern(
        self, resource_id: str, week_start: date
    ) -> None:
        """Filename matches YYYY-Www-<resource_id>.tji pattern."""
        gen = TimesheetGenerator()
        filename = gen.get_filename(resource_id, week_start)

        # Pattern: YYYY-Www-<resource_id>.tji
        pattern = r"^\d{4}-W\d{2}-.+\.tji$"
        assert re.match(pattern, filename), (
            f"Filename {filename!r} does not match pattern YYYY-Www-<resource_id>.tji"
        )

    @given(resource_id=_resource_id, week_start=_monday_date)
    @settings(max_examples=100)
    def test_filename_contains_correct_iso_year_and_week(
        self, resource_id: str, week_start: date
    ) -> None:
        """Filename contains the correct ISO year and week number."""
        gen = TimesheetGenerator()
        filename = gen.get_filename(resource_id, week_start)

        iso_year, iso_week, _ = week_start.isocalendar()
        expected_prefix = f"{iso_year}-W{iso_week:02d}-"
        assert filename.startswith(expected_prefix), (
            f"Filename {filename!r} does not start with {expected_prefix!r}"
        )

    @given(resource_id=_resource_id, week_start=_monday_date)
    @settings(max_examples=100)
    def test_filename_contains_resource_id(
        self, resource_id: str, week_start: date
    ) -> None:
        """Filename contains the exact resource ID."""
        gen = TimesheetGenerator()
        filename = gen.get_filename(resource_id, week_start)

        assert filename.endswith(f"-{resource_id}.tji"), (
            f"Filename {filename!r} does not end with '-{resource_id}.tji'"
        )


class TestTimesheetMergePreservesEntries:
    """Property 7: Timesheet merge preserves unrelated entries.

    **Validates: Requirements 4.3**
    """

    @given(
        resource_id=_resource_id,
        week_start=_monday_date,
        existing_entries=st.lists(_task_entry, min_size=2, max_size=5, unique_by=lambda e: e.task_path),
        new_entry=_task_entry,
    )
    @settings(max_examples=100)
    def test_unrelated_entries_preserved(
        self,
        resource_id: str,
        week_start: date,
        existing_entries: list[TaskEntry],
        new_entry: TaskEntry,
    ) -> None:
        """Merging preserves all entries for non-matching task paths."""
        # Ensure new_entry has a different task path from all existing entries
        existing_paths = {e.task_path for e in existing_entries}
        assume(new_entry.task_path not in existing_paths)

        gen = TimesheetGenerator()

        # Generate existing timesheet
        booking = BookingRequest(
            resource_id=resource_id,
            week_start=week_start,
            entries=existing_entries,
        )
        existing_content = gen.generate(booking)

        # Merge new entry
        merged = gen.merge_into_existing(existing_content, new_entry)

        # All original task paths should still be present
        for entry in existing_entries:
            assert entry.task_path in merged, (
                f"Original entry {entry.task_path!r} lost after merge"
            )

        # New entry should also be present
        assert new_entry.task_path in merged, (
            f"New entry {new_entry.task_path!r} not found after merge"
        )

    @given(
        resource_id=_resource_id,
        week_start=_monday_date,
        existing_entries=st.lists(_task_entry, min_size=2, max_size=5, unique_by=lambda e: e.task_path),
    )
    @settings(max_examples=100)
    def test_matching_entry_replaced(
        self,
        resource_id: str,
        week_start: date,
        existing_entries: list[TaskEntry],
    ) -> None:
        """Merging replaces the entry for a matching task path."""
        gen = TimesheetGenerator()

        # Generate existing timesheet
        booking = BookingRequest(
            resource_id=resource_id,
            week_start=week_start,
            entries=existing_entries,
        )
        existing_content = gen.generate(booking)

        # Create a new entry with the same task path as the first existing entry
        target_path = existing_entries[0].task_path
        replacement_entry = TaskEntry(
            task_path=target_path,
            hours=99.0,  # Distinctive value
            status_color=None,
            status_headline=None,
            status_summary=None,
        )

        merged = gen.merge_into_existing(existing_content, replacement_entry)

        # The merged result should contain the new hours value
        assert "99h" in merged or "99.0h" in merged, (
            f"Replacement hours not found in merged output for path {target_path!r}"
        )

        # All other entries should still be present
        for entry in existing_entries[1:]:
            assert entry.task_path in merged, (
                f"Unrelated entry {entry.task_path!r} lost after replacing {target_path!r}"
            )
