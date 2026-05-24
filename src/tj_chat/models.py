"""Pydantic data models for the LLM Agent Chat service.

Defines all structured data types used across the chat service,
including conversation messages, tool calls, project data, and
request/response models.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, Field


class FunctionCall(BaseModel):
    """Function call details within a tool call."""

    name: str
    arguments: str  # JSON string


class ToolCallMessage(BaseModel):
    """A tool call within an assistant message."""

    id: str
    type: str = "function"
    function: FunctionCall


class Message(BaseModel):
    """A single message in the conversation history."""

    role: str  # "system", "user", "assistant", "tool"
    content: str | None = None
    tool_calls: list[ToolCallMessage] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ToolCall(BaseModel):
    """Parsed tool call ready for execution."""

    id: str
    name: str
    arguments: dict


class ToolResult(BaseModel):
    """Result of a tool execution."""

    tool_call_id: str
    success: bool
    content: str
    requires_confirmation: bool = False
    confirmation_summary: str | None = None


class ToolAction(BaseModel):
    """Summary of a tool action taken during response generation."""

    tool_name: str
    summary: str


class ConfirmationRequest(BaseModel):
    """A write operation awaiting user confirmation."""

    file_path: str
    operation_type: str  # "create", "modify", "delete"
    description: str
    pending_content: str


class AgentResponse(BaseModel):
    """Complete response from the agent including any tool actions."""

    text: str
    tool_actions: list[ToolAction] = Field(default_factory=list)
    confirmation_request: ConfirmationRequest | None = None


class ConnectionResult(BaseModel):
    """Result of connecting to LM Studio."""

    success: bool
    model_name: str | None = None
    error: str | None = None


class CompilerResult(BaseModel):
    """Result of running the tj3 compiler."""

    success: bool
    stdout: str
    stderr: str


class SystemStatus(BaseModel):
    """System status for the admin page."""

    project_file: str
    project_exists: bool
    report_count: int
    timesheet_count: int
    lm_studio_connected: bool


class ReportFile(BaseModel):
    """A generated report file available for viewing."""

    name: str
    path: str
    size: int
    modified: str


class BookingStatus(StrEnum):
    """Timesheet task status colors."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class TaskEntry(BaseModel):
    """A single task entry within a timesheet."""

    task_path: str
    hours: float = Field(gt=0)
    status_color: BookingStatus | None = None
    status_headline: str | None = None
    status_summary: str | None = None


class BookingRequest(BaseModel):
    """Request to write a timesheet booking."""

    resource_id: str
    week_start: date  # Monday of the ISO week
    entries: list[TaskEntry]


class JournalEntryRequest(BaseModel):
    """Request to write a journal entry."""

    task_path: str | None = None
    entry_date: date
    author: str
    headline: str = Field(max_length=120)
    summary: str | None = None


class ReportType(StrEnum):
    """Supported TaskJuggler report types."""

    TASK = "taskreport"
    RESOURCE = "resourcereport"
    ACCOUNT = "accountreport"
    TEXT = "textreport"
    STATUS = "statusreport"


class ReportRequest(BaseModel):
    """Request to write a report definition."""

    report_id: str
    report_type: ReportType
    title: str
    columns: list[str]
    formats: list[str] = Field(default_factory=lambda: ["html"])
    sort_order: str | None = None
    hide_expression: str | None = None
    time_scale: str | None = None
    caption: str | None = None


class TaskInfo(BaseModel):
    """Parsed task information from project files."""

    path: str  # Full dotted path e.g. "acme.development.backend_api.schema"
    name: str
    effort: str | None = None
    allocations: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    is_milestone: bool = False
    end_date: str | None = None  # Planned end date in YYYY-MM-DD format
    complete: int | None = None  # Completion percentage (0-100)


class OverdueTask(BaseModel):
    """A task that is past its planned end date without full completion."""

    task: TaskInfo
    days_overdue: int


class ResourceInfo(BaseModel):
    """Parsed resource information from project files."""

    id: str
    name: str
    rate: float | None = None
    working_hours: str | None = None


class TaskMatch(BaseModel):
    """A task matching a search query with similarity score."""

    task: TaskInfo
    score: float


class ResourceMatch(BaseModel):
    """A resource matching a search query."""

    resource: ResourceInfo
    exact: bool


class ProjectSummary(BaseModel):
    """Summary of the project structure for the system prompt."""

    project_name: str
    start_date: str
    end_date: str
    now_date: str
    file_tree: list[str]
    resource_ids: list[str]
    top_level_tasks: list[str]


class PathSecurityError(Exception):
    """Raised when a file path escapes the project boundary."""

    def __init__(self, path: str, project_root: str) -> None:
        super().__init__(
            f"Path '{path}' is outside the allowed project directory '{project_root}'"
        )
        self.path = path
        self.project_root = project_root


class TaskRequest(BaseModel):
    """Request to create a new TaskJuggler task definition."""

    task_id: str
    name: str
    effort: str
    allocation: str | list[str]
    depends: list[str] | None = None
    priority: int | None = None


class DocSection(BaseModel):
    """A section from the bundled TaskJuggler reference documentation."""

    title: str  # Section heading, e.g. "task", "resource", "timesheet"
    content: str  # Full text content of the section
    relevance_score: float = Field(ge=0.0, le=1.0)  # Match relevance to query
