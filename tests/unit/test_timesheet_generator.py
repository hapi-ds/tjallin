"""Unit tests for the TimesheetGenerator class."""

from datetime import date

import pytest

from tj_chat.generators import TimesheetGenerator
from tj_chat.models import BookingRequest, BookingStatus, TaskEntry


@pytest.fixture
def generator() -> TimesheetGenerator:
    """Create a TimesheetGenerator instance."""
    return TimesheetGenerator()


class TestGenerate:
    """Tests for TimesheetGenerator.generate()."""

    def test_single_entry_no_status(self, generator: TimesheetGenerator) -> None:
        booking = BookingRequest(
            resource_id="alice",
            week_start=date(2024, 1, 29),
            entries=[
                TaskEntry(task_path="acme.development.backend_api.schema", hours=40),
            ],
        )
        result = generator.generate(booking)
        assert result == (
            "timesheet alice 2024-01-29 +1w {\n"
            "  task acme.development.backend_api.schema {\n"
            "    work 40h\n"
            "  }\n"
            "}\n"
        )

    def test_single_entry_with_status_no_summary(self, generator: TimesheetGenerator) -> None:
        booking = BookingRequest(
            resource_id="bob",
            week_start=date(2024, 2, 5),
            entries=[
                TaskEntry(
                    task_path="acme.development.frontend.components",
                    hours=24,
                    status_color=BookingStatus.YELLOW,
                    status_headline="In progress",
                ),
            ],
        )
        result = generator.generate(booking)
        assert 'status yellow "In progress"' in result
        assert "summary" not in result

    def test_single_entry_with_status_and_summary(self, generator: TimesheetGenerator) -> None:
        booking = BookingRequest(
            resource_id="alice",
            week_start=date(2024, 1, 29),
            entries=[
                TaskEntry(
                    task_path="acme.development.backend_api.schema",
                    hours=32,
                    status_color=BookingStatus.GREEN,
                    status_headline="Schema design completed",
                    status_summary="Finalized database schema.",
                ),
            ],
        )
        result = generator.generate(booking)
        assert 'status green "Schema design completed" {' in result
        assert 'summary "Finalized database schema."' in result

    def test_multiple_entries(self, generator: TimesheetGenerator) -> None:
        booking = BookingRequest(
            resource_id="alice",
            week_start=date(2024, 1, 29),
            entries=[
                TaskEntry(
                    task_path="acme.development.backend_api.schema",
                    hours=32,
                    status_color=BookingStatus.GREEN,
                    status_headline="Completed",
                ),
                TaskEntry(
                    task_path="acme.development.backend_api.endpoints",
                    hours=8,
                    status_color=BookingStatus.YELLOW,
                    status_headline="Started",
                ),
            ],
        )
        result = generator.generate(booking)
        assert result.count("task ") == 2
        assert "work 32h" in result
        assert "work 8h" in result

    def test_fractional_hours(self, generator: TimesheetGenerator) -> None:
        booking = BookingRequest(
            resource_id="dave",
            week_start=date(2024, 3, 4),
            entries=[
                TaskEntry(task_path="acme.testing.unit_tests", hours=4.5),
            ],
        )
        result = generator.generate(booking)
        assert "work 4.5h" in result

    def test_header_format(self, generator: TimesheetGenerator) -> None:
        booking = BookingRequest(
            resource_id="alice",
            week_start=date(2024, 1, 29),
            entries=[TaskEntry(task_path="acme.dev", hours=8)],
        )
        result = generator.generate(booking)
        assert result.startswith("timesheet alice 2024-01-29 +1w {")


class TestMergeIntoExisting:
    """Tests for TimesheetGenerator.merge_into_existing()."""

    def test_replace_existing_task(self, generator: TimesheetGenerator) -> None:
        existing = (
            "timesheet alice 2024-01-29 +1w {\n"
            "  task acme.development.backend_api.schema {\n"
            "    work 32h\n"
            '    status green "Old status"\n'
            "  }\n"
            "  task acme.development.backend_api.endpoints {\n"
            "    work 8h\n"
            "  }\n"
            "}\n"
        )
        new_entry = TaskEntry(
            task_path="acme.development.backend_api.schema",
            hours=40,
            status_color=BookingStatus.GREEN,
            status_headline="Completed",
        )
        result = generator.merge_into_existing(existing, new_entry)
        assert "work 40h" in result
        assert 'status green "Completed"' in result
        # The other task should be preserved
        assert "acme.development.backend_api.endpoints" in result
        assert "work 8h" in result
        # Old status should be gone
        assert "Old status" not in result

    def test_add_new_task(self, generator: TimesheetGenerator) -> None:
        existing = (
            "timesheet alice 2024-01-29 +1w {\n"
            "  task acme.development.backend_api.schema {\n"
            "    work 32h\n"
            "  }\n"
            "}\n"
        )
        new_entry = TaskEntry(
            task_path="acme.development.backend_api.endpoints",
            hours=8,
        )
        result = generator.merge_into_existing(existing, new_entry)
        assert "acme.development.backend_api.schema" in result
        assert "acme.development.backend_api.endpoints" in result
        assert "work 8h" in result

    def test_preserves_header(self, generator: TimesheetGenerator) -> None:
        existing = (
            "timesheet bob 2024-02-05 +1w {\n"
            "  task acme.testing {\n"
            "    work 20h\n"
            "  }\n"
            "}\n"
        )
        new_entry = TaskEntry(task_path="acme.dev", hours=10)
        result = generator.merge_into_existing(existing, new_entry)
        assert result.startswith("timesheet bob 2024-02-05 +1w {")


class TestGetFilename:
    """Tests for TimesheetGenerator.get_filename()."""

    def test_standard_week(self, generator: TimesheetGenerator) -> None:
        result = generator.get_filename("alice", date(2024, 1, 29))
        assert result == "2024-W05-alice.tji"

    def test_first_week(self, generator: TimesheetGenerator) -> None:
        result = generator.get_filename("bob", date(2024, 1, 1))
        assert result == "2024-W01-bob.tji"

    def test_week_zero_padded(self, generator: TimesheetGenerator) -> None:
        result = generator.get_filename("alice", date(2024, 1, 8))
        assert result == "2024-W02-alice.tji"

    def test_high_week_number(self, generator: TimesheetGenerator) -> None:
        result = generator.get_filename("dave", date(2024, 12, 23))
        assert result == "2024-W52-dave.tji"

    def test_iso_year_differs_from_calendar_year(self, generator: TimesheetGenerator) -> None:
        """Dec 30, 2024 is ISO week 1 of 2025."""
        result = generator.get_filename("alice", date(2024, 12, 30))
        assert result == "2025-W01-alice.tji"
