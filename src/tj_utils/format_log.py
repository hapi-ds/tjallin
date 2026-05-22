"""Log line formatting for TaskJuggler Docker Compose services.

Produces structured log output in the format:
    [SERVICE_NAME] [ISO8601_TIMESTAMP] [LEVEL] message

All services use this format for consistent, parseable log output
collected by Docker's logging driver.
"""

from __future__ import annotations

from datetime import UTC, datetime


def format_log(
    service_name: str,
    level: str,
    message: str,
    timestamp: datetime | None = None,
) -> str:
    """Format a log line with service name, ISO 8601 timestamp, and level.

    Produces output in the format:
        [SERVICE_NAME] [ISO8601_TIMESTAMP] [LEVEL] message

    Args:
        service_name: Name of the service producing the log (e.g., "tj-core").
        level: Log level (DEBUG, INFO, WARNING, ERROR).
        message: The log message content.
        timestamp: Optional timestamp; defaults to current UTC time if not provided.

    Returns:
        Formatted log line string.

    Examples:
        >>> format_log("tj-core", "INFO", "Compilation complete")
        '[tj-core] [2024-01-15T10:30:00+00:00] [INFO] Compilation complete'
    """
    if timestamp is None:
        timestamp = datetime.now(UTC)

    iso_timestamp = timestamp.isoformat()

    return f"[{service_name}] [{iso_timestamp}] [{level}] {message}"
