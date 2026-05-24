"""Property-based tests for report generation.

**Validates: Requirements 9.1**

Property 9: Report generation produces valid structure.
- For any valid ReportRequest with a report ID, report type, title, and
  column list, the generated output SHALL be a syntactically valid
  TaskJuggler report definition of the specified type containing the
  report ID, title as headline, and all specified columns.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tj_chat.generators import ReportGenerator
from tj_chat.models import ReportRequest, ReportType

# Strategy for valid TaskJuggler identifiers (alphanumeric + underscore, starts with letter)
_id_char = st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_")
_tj_identifier = st.builds(
    lambda first, rest: first + rest,
    st.sampled_from("abcdefghijklmnopqrstuvwxyz"),
    st.text(alphabet=_id_char, min_size=1, max_size=15),
)

# Strategy for report titles (non-empty, no double quotes to avoid escaping issues)
_report_title = st.text(
    alphabet=st.characters(
        categories=("L", "N", "P", "Z"),
        exclude_characters='"',
    ),
    min_size=1,
    max_size=60,
).filter(lambda s: s.strip() != "")

# Strategy for column names (valid TJ column identifiers)
_column_name = st.sampled_from([
    "name", "start", "end", "effort", "duration", "complete",
    "cost", "revenue", "chart", "resources", "responsible",
    "status", "id", "hierarchindex", "alerts", "bsi",
])

# Strategy for report types
_report_type = st.sampled_from(list(ReportType))

# Strategy for format values
_format_value = st.sampled_from(["html", "csv", "niku"])


@st.composite
def report_request_strategy(draw: st.DrawFn) -> ReportRequest:
    """Generate a valid ReportRequest with required fields."""
    report_id = draw(_tj_identifier)
    report_type = draw(_report_type)
    title = draw(_report_title)
    columns = draw(st.lists(_column_name, min_size=1, max_size=6, unique=True))
    formats = draw(st.lists(_format_value, min_size=1, max_size=3, unique=True))

    # Optional fields
    sort_order = draw(st.one_of(st.none(), st.just("plan.start up")))
    hide_expression = draw(st.one_of(st.none(), st.just("~isleaf()")))
    time_scale = draw(st.one_of(st.none(), st.sampled_from(["day", "week", "month", "quarter"])))
    caption = draw(st.one_of(st.none(), _report_title))

    return ReportRequest(
        report_id=report_id,
        report_type=report_type,
        title=title,
        columns=columns,
        formats=formats,
        sort_order=sort_order,
        hide_expression=hide_expression,
        time_scale=time_scale,
        caption=caption,
    )


class TestReportGenerationProducesValidStructure:
    """Property 9: Report generation produces valid structure.

    **Validates: Requirements 9.1**
    """

    @given(report=report_request_strategy())
    @settings(max_examples=200)
    def test_output_starts_with_report_type_and_id(
        self, report: ReportRequest
    ) -> None:
        """Generated output opens with the correct report type keyword and ID."""
        generator = ReportGenerator()
        output = generator.generate(report)

        first_line = output.split("\n")[0]
        assert first_line.startswith(f"{report.report_type.value} {report.report_id} ")

    @given(report=report_request_strategy())
    @settings(max_examples=200)
    def test_output_contains_title_as_headline(
        self, report: ReportRequest
    ) -> None:
        """Generated output contains the title as a quoted headline string."""
        generator = ReportGenerator()
        output = generator.generate(report)

        first_line = output.split("\n")[0]
        assert f'"{report.title}"' in first_line

    @given(report=report_request_strategy())
    @settings(max_examples=200)
    def test_output_contains_all_specified_columns(
        self, report: ReportRequest
    ) -> None:
        """Generated output includes all columns from the request."""
        generator = ReportGenerator()
        output = generator.generate(report)

        # Find the columns line
        columns_line = None
        for line in output.split("\n"):
            stripped = line.strip()
            if stripped.startswith("columns "):
                columns_line = stripped
                break

        assert columns_line is not None, "Output must contain a 'columns' line"

        for col in report.columns:
            assert col in columns_line, f"Column '{col}' missing from output"

    @given(report=report_request_strategy())
    @settings(max_examples=200)
    def test_output_is_valid_block_structure(
        self, report: ReportRequest
    ) -> None:
        """Generated output has proper opening and closing block structure."""
        generator = ReportGenerator()
        output = generator.generate(report)

        lines = output.split("\n")
        # First line must end with opening brace
        assert lines[0].rstrip().endswith("{")
        # Last line must be closing brace
        assert lines[-1].strip() == "}"
        # The output forms a single top-level block: first line opens, last line closes
        assert lines[0].rstrip()[-1] == "{"
        assert lines[-1].strip() == "}"

    @given(report=report_request_strategy())
    @settings(max_examples=200)
    def test_output_contains_report_id(
        self, report: ReportRequest
    ) -> None:
        """Generated output contains the report ID."""
        generator = ReportGenerator()
        output = generator.generate(report)

        assert report.report_id in output

    @given(report=report_request_strategy())
    @settings(max_examples=100)
    def test_optional_fields_included_when_present(
        self, report: ReportRequest
    ) -> None:
        """Optional fields appear in output only when set in the request."""
        generator = ReportGenerator()
        output = generator.generate(report)

        if report.sort_order is not None:
            assert f"sorttasks {report.sort_order}" in output
        else:
            assert "sorttasks" not in output

        if report.hide_expression is not None:
            assert f"hidetask {report.hide_expression}" in output
        else:
            assert "hidetask" not in output

        if report.time_scale is not None:
            assert f"timescale {report.time_scale}" in output
        else:
            assert "timescale" not in output

        if report.caption is not None:
            assert f'caption "{report.caption}"' in output
        else:
            assert "caption" not in output
