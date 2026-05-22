"""Environment variable validation for TaskJuggler Docker Compose services.

Uses Pydantic for structured validation of required and optional environment
variables, including port ranges, log levels, and IANA timezone identifiers.
"""

from __future__ import annotations

import zoneinfo
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Valid log levels accepted by the system
VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})

# Required environment variables that must be non-empty
REQUIRED_ENV_VARS = ("TJ_SMTP_HOST", "TJ_SMTP_PORT", "TJ_MAIL_DOMAIN")


class EnvValidationResult(BaseModel):
    """Result of environment variable validation.

    Attributes:
        valid: Whether all validations passed.
        errors: List of error messages for failed validations.
        warnings: List of warning messages for non-fatal issues.
        effective_log_level: The resolved log level after fallback logic.
    """

    valid: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    effective_log_level: str = "INFO"


def validate_required_vars(env: dict[str, Any]) -> list[str]:
    """Check that all required environment variables are present and non-empty.

    Args:
        env: Dictionary of environment variable names to values.

    Returns:
        List of error messages for missing or empty required variables.
    """
    errors: list[str] = []
    for var in REQUIRED_ENV_VARS:
        value = env.get(var)
        if value is None or str(value).strip() == "":
            errors.append(f"Required variable {var} is not set")
    return errors


def validate_port(value: Any, var_name: str = "TJ_WEB_PORT") -> tuple[int | None, str | None]:
    """Validate that a value is a valid port number (1-65535).

    Args:
        value: The value to validate as a port number.
        var_name: Name of the variable for error messages.

    Returns:
        Tuple of (parsed port or None, error message or None).
    """
    if value is None:
        return None, None
    try:
        port = int(value)
    except (ValueError, TypeError):
        return None, f"{var_name} must be a valid integer, got: {value!r}"
    if port < 1 or port > 65535:
        return None, f"{var_name} must be between 1 and 65535, got: {port}"
    return port, None


def validate_log_level(value: Any) -> tuple[str, str | None]:
    """Validate log level, falling back to INFO with a warning if invalid.

    Args:
        value: The log level string to validate.

    Returns:
        Tuple of (effective log level, warning message or None).
    """
    if value is None or str(value).strip() == "":
        return "INFO", None
    level = str(value).strip().upper()
    if level in VALID_LOG_LEVELS:
        return level, None
    return "INFO", (
        f"Invalid TJ_LOG_LEVEL value '{value}', falling back to INFO. "
        f"Accepted values: {', '.join(sorted(VALID_LOG_LEVELS))}"
    )


def validate_timezone(value: Any) -> tuple[str, str | None]:
    """Validate that a value is a valid IANA timezone identifier.

    Args:
        value: The timezone string to validate.

    Returns:
        Tuple of (timezone string, error message or None).
    """
    if value is None or str(value).strip() == "":
        return "UTC", None
    tz_str = str(value).strip()
    try:
        zoneinfo.ZoneInfo(tz_str)
        return tz_str, None
    except (KeyError, zoneinfo.ZoneInfoNotFoundError):
        return tz_str, f"TJ_TIMEZONE '{tz_str}' is not a valid IANA timezone identifier"


def validate_env(env: dict[str, Any]) -> EnvValidationResult:
    """Validate all environment variables for the TaskJuggler stack.

    Performs comprehensive validation including:
    - Required variables are present and non-empty
    - Port numbers are in valid range (1-65535)
    - Log level is valid (falls back to INFO with warning if not)
    - Timezone is a valid IANA identifier

    Args:
        env: Dictionary of environment variable names to values.

    Returns:
        EnvValidationResult with validation outcome, errors, and warnings.
    """
    result = EnvValidationResult()

    # Check required variables
    required_errors = validate_required_vars(env)
    result.errors.extend(required_errors)

    # Validate port
    port_value = env.get("TJ_WEB_PORT")
    if port_value is not None:
        _, port_error = validate_port(port_value)
        if port_error:
            result.errors.append(port_error)

    # Validate log level
    log_level_value = env.get("TJ_LOG_LEVEL")
    effective_level, log_warning = validate_log_level(log_level_value)
    result.effective_log_level = effective_level
    if log_warning:
        result.warnings.append(log_warning)

    # Validate timezone
    tz_value = env.get("TJ_TIMEZONE")
    _, tz_error = validate_timezone(tz_value)
    if tz_error:
        result.errors.append(tz_error)

    # Set overall validity
    result.valid = len(result.errors) == 0

    return result


class TJEnvironment(BaseModel):
    """Pydantic model for TaskJuggler environment variable validation.

    This model validates all environment variables using Pydantic's
    built-in validation. Use `from_env()` to create from a dict of
    environment variables.

    Attributes:
        tj_smtp_host: SMTP relay host (required, non-empty).
        tj_smtp_port: SMTP relay port (required, 1-65535).
        tj_mail_domain: Mail domain for receiving timesheets (required, non-empty).
        tj_web_port: Web interface port (default 8080, 1-65535).
        tj_log_level: Log level (default INFO, validated against allowed set).
        tj_timezone: IANA timezone identifier (default UTC).
        tj_task_timeout: Task timeout in seconds (default 300, must be > 0).
    """

    tj_smtp_host: str
    tj_smtp_port: int = Field(ge=1, le=65535)
    tj_mail_domain: str
    tj_web_port: int = Field(default=8080, ge=1, le=65535)
    tj_log_level: str = "INFO"
    tj_timezone: str = "UTC"
    tj_task_timeout: int = Field(default=300, gt=0)

    @field_validator("tj_smtp_host", "tj_mail_domain")
    @classmethod
    def must_be_non_empty(cls, v: str, info: Any) -> str:
        """Validate that required string fields are non-empty."""
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be non-empty")
        return v.strip()

    @field_validator("tj_log_level")
    @classmethod
    def validate_log_level_field(cls, v: str) -> str:
        """Validate log level is in the accepted set."""
        upper = v.strip().upper() if v else "INFO"
        if upper not in VALID_LOG_LEVELS:
            # Fall back to INFO — caller should check warnings via validate_env()
            return "INFO"
        return upper

    @field_validator("tj_timezone")
    @classmethod
    def validate_timezone_field(cls, v: str) -> str:
        """Validate timezone is a valid IANA identifier."""
        if not v or not v.strip():
            return "UTC"
        tz_str = v.strip()
        try:
            zoneinfo.ZoneInfo(tz_str)
            return tz_str
        except (KeyError, zoneinfo.ZoneInfoNotFoundError):
            raise ValueError(f"'{tz_str}' is not a valid IANA timezone identifier")
