"""Task execution wrapper for TaskJuggler cron service.

Provides lock file management, timeout handling, stderr truncation,
and overlap detection for scheduled task execution.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from tj_utils.format_log import format_log

# Maximum stderr characters to include in failure logs
MAX_STDERR_CHARS = 1000

# Default task timeout in seconds
DEFAULT_TIMEOUT_SECONDS = 300


@dataclass
class TaskResult:
    """Result of a task execution attempt.

    Attributes:
        executed: Whether the task was actually executed (False if skipped).
        success: Whether the task completed successfully.
        exit_code: Exit code from the task process (None if not executed).
        stderr_output: Captured stderr output (truncated to 1000 chars).
        skipped: Whether execution was skipped due to overlap.
        timed_out: Whether the task was killed due to timeout.
        log_messages: Log messages generated during execution.
    """

    executed: bool = False
    success: bool = False
    exit_code: int | None = None
    stderr_output: str = ""
    skipped: bool = False
    timed_out: bool = False
    log_messages: list[str] = field(default_factory=list)


def truncate_stderr(stderr: str, max_chars: int = MAX_STDERR_CHARS) -> str:
    """Truncate stderr output to the specified maximum character count.

    Args:
        stderr: The full stderr output string.
        max_chars: Maximum number of characters to keep (default 1000).

    Returns:
        Truncated stderr string, with no more than max_chars characters.
    """
    if len(stderr) <= max_chars:
        return stderr
    return stderr[:max_chars]


def check_lock_file(lock_file_path: str | Path) -> tuple[bool, str | None]:
    """Check if a lock file exists, indicating a task is already running.

    Args:
        lock_file_path: Path to the lock file.

    Returns:
        Tuple of (lock_exists, lock_content or None).
    """
    path = Path(lock_file_path)
    if path.exists():
        try:
            content = path.read_text().strip()
            return True, content
        except OSError:
            return True, None
    return False, None


def create_lock_file(lock_file_path: str | Path) -> None:
    """Create a lock file with PID and start timestamp.

    Args:
        lock_file_path: Path where the lock file should be created.
    """
    path = Path(lock_file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat()
    content = f"PID={os.getpid()} STARTED={timestamp}"
    path.write_text(content)


def remove_lock_file(lock_file_path: str | Path) -> None:
    """Remove a lock file.

    Args:
        lock_file_path: Path to the lock file to remove.
    """
    path = Path(lock_file_path)
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def parse_lock_start_time(lock_content: str) -> datetime | None:
    """Parse the start timestamp from lock file content.

    Args:
        lock_content: Content of the lock file (format: "PID=<pid> STARTED=<iso>").

    Returns:
        Parsed datetime or None if parsing fails.
    """
    try:
        for part in lock_content.split():
            if part.startswith("STARTED="):
                iso_str = part[len("STARTED="):]
                return datetime.fromisoformat(iso_str)
    except (ValueError, IndexError):
        pass
    return None


def calculate_elapsed_time(start_time: datetime) -> float:
    """Calculate elapsed time in seconds since the given start time.

    Args:
        start_time: The start time to measure from.

    Returns:
        Elapsed time in seconds.
    """
    now = datetime.now(UTC)
    return (now - start_time).total_seconds()


def format_task_success_log(
    service_name: str,
    task_name: str,
    timestamp: datetime | None = None,
) -> str:
    """Format a success log entry for a completed task.

    Args:
        service_name: Name of the service (e.g., "tj-cron").
        task_name: Name of the completed task.
        timestamp: Optional timestamp; defaults to current UTC time.

    Returns:
        Formatted log line for successful task completion.
    """
    return format_log(
        service_name=service_name,
        level="INFO",
        message=f"Task '{task_name}' completed successfully",
        timestamp=timestamp,
    )


def format_task_failure_log(
    service_name: str,
    task_name: str,
    exit_code: int,
    stderr: str,
    timestamp: datetime | None = None,
) -> str:
    """Format a failure log entry for a failed task.

    Includes the task name, exit code, and first 1000 characters of stderr.

    Args:
        service_name: Name of the service (e.g., "tj-cron").
        task_name: Name of the failed task.
        exit_code: Exit code from the task process.
        stderr: Full stderr output (will be truncated to 1000 chars).
        timestamp: Optional timestamp; defaults to current UTC time.

    Returns:
        Formatted log line for task failure.
    """
    truncated = truncate_stderr(stderr)
    message = f"Task '{task_name}' failed: exit code {exit_code}"
    if truncated:
        message += f"\n{truncated}"
    return format_log(
        service_name=service_name,
        level="ERROR",
        message=message,
        timestamp=timestamp,
    )


def format_task_timeout_log(
    service_name: str,
    task_name: str,
    timeout_seconds: int,
    timestamp: datetime | None = None,
) -> str:
    """Format a timeout log entry for a task that exceeded its time limit.

    Args:
        service_name: Name of the service (e.g., "tj-cron").
        task_name: Name of the timed-out task.
        timeout_seconds: The configured timeout that was exceeded.
        timestamp: Optional timestamp; defaults to current UTC time.

    Returns:
        Formatted log line for task timeout.
    """
    return format_log(
        service_name=service_name,
        level="ERROR",
        message=f"Task '{task_name}' timed out after {timeout_seconds}s",
        timestamp=timestamp,
    )


def format_task_overlap_log(
    service_name: str,
    task_name: str,
    elapsed_seconds: float,
    timestamp: datetime | None = None,
) -> str:
    """Format a warning log entry for a skipped overlapping task execution.

    Args:
        service_name: Name of the service (e.g., "tj-cron").
        task_name: Name of the task that was skipped.
        elapsed_seconds: Time in seconds since the running instance started.
        timestamp: Optional timestamp; defaults to current UTC time.

    Returns:
        Formatted log line for overlap warning.
    """
    return format_log(
        service_name=service_name,
        level="WARNING",
        message=(
            f"Task '{task_name}' skipped: previous execution still running "
            f"(elapsed: {elapsed_seconds:.1f}s)"
        ),
        timestamp=timestamp,
    )
