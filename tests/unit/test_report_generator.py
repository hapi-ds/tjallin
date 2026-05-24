"""Unit tests for the ReportGenerator class."""

from tj_chat.generators import ReportGenerator
from tj_chat.models import ReportRequest, ReportType


class TestReportGenerator:
    """Tests for ReportGenerator.generate()."""

    def setup_method(self) -> None:
        self.generator = ReportGenerator()

    def test_basic_taskreport(self) -> None:
        """Generate a minimal taskreport with required fields only."""
        request = ReportRequest(
            report_id="GanttChart",
            report_type=ReportType.TASK,
            title="Gantt Chart",
            columns=["bsi", "name", "start", "end", "chart"],
        )
        result = self.generator.generate(request)

        assert 'taskreport GanttChart "Gantt Chart" {' in result
        assert "  formats html" in result
        assert "  columns bsi, name, start, end, chart" in result
        assert result.endswith("}")

    def test_resourcereport_with_all_options(self) -> None:
        """Generate a resourcereport with all optional attributes."""
        request = ReportRequest(
            report_id="ResourceUsage",
            report_type=ReportType.RESOURCE,
            title="Resource Usage",
            columns=["no", "name", "effort", "weekly"],
            formats=["html", "csv"],
            sort_order="name.up",
            hide_expression="~isleaf()",
            time_scale="week",
            caption="Weekly resource allocation.",
        )
        result = self.generator.generate(request)

        assert 'resourcereport ResourceUsage "Resource Usage" {' in result
        assert "  formats html, csv" in result
        assert "  columns no, name, effort, weekly" in result
        assert "  sorttasks name.up" in result
        assert "  hidetask ~isleaf()" in result
        assert "  timescale week" in result
        assert '  caption "Weekly resource allocation."' in result
        assert result.endswith("}")

    def test_accountreport(self) -> None:
        """Generate an accountreport."""
        request = ReportRequest(
            report_id="CostReport",
            report_type=ReportType.ACCOUNT,
            title="Cost Report",
            columns=["no", "name", "cost", "weekly"],
        )
        result = self.generator.generate(request)

        assert 'accountreport CostReport "Cost Report" {' in result
        assert "  columns no, name, cost, weekly" in result

    def test_textreport(self) -> None:
        """Generate a textreport."""
        request = ReportRequest(
            report_id="Overview",
            report_type=ReportType.TEXT,
            title="Project Overview",
            columns=["name"],
            caption="Overview of the project.",
        )
        result = self.generator.generate(request)

        assert 'textreport Overview "Project Overview" {' in result
        assert '  caption "Overview of the project."' in result

    def test_statusreport(self) -> None:
        """Generate a statusreport."""
        request = ReportRequest(
            report_id="StatusReport",
            report_type=ReportType.STATUS,
            title="Weekly Status",
            columns=["name", "journal"],
        )
        result = self.generator.generate(request)

        assert 'statusreport StatusReport "Weekly Status" {' in result
        assert "  columns name, journal" in result

    def test_no_optional_attributes_omitted(self) -> None:
        """Optional attributes should not appear when not set."""
        request = ReportRequest(
            report_id="Simple",
            report_type=ReportType.TASK,
            title="Simple Report",
            columns=["name", "start", "end"],
        )
        result = self.generator.generate(request)

        assert "sorttasks" not in result
        assert "hidetask" not in result
        assert "timescale" not in result
        assert "caption" not in result

    def test_default_format_is_html(self) -> None:
        """Default format should be html when not specified."""
        request = ReportRequest(
            report_id="Default",
            report_type=ReportType.TASK,
            title="Default Format",
            columns=["name"],
        )
        result = self.generator.generate(request)

        assert "  formats html" in result

    def test_multiple_formats(self) -> None:
        """Multiple formats should be comma-separated."""
        request = ReportRequest(
            report_id="Multi",
            report_type=ReportType.TASK,
            title="Multi Format",
            columns=["name"],
            formats=["html", "csv"],
        )
        result = self.generator.generate(request)

        assert "  formats html, csv" in result

    def test_output_structure_ordering(self) -> None:
        """Verify the ordering of lines in the output."""
        request = ReportRequest(
            report_id="Ordered",
            report_type=ReportType.TASK,
            title="Ordered Report",
            columns=["name", "effort"],
            sort_order="plan.start.up",
            hide_expression="~isleaf()",
            time_scale="day",
            caption="Test caption",
        )
        result = self.generator.generate(request)
        lines = result.split("\n")

        assert lines[0] == 'taskreport Ordered "Ordered Report" {'
        assert lines[1] == "  formats html"
        assert lines[2] == "  columns name, effort"
        assert lines[3] == "  sorttasks plan.start.up"
        assert lines[4] == "  hidetask ~isleaf()"
        assert lines[5] == "  timescale day"
        assert lines[6] == '  caption "Test caption"'
        assert lines[7] == "}"
