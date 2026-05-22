"""TaskJuggler Docker Compose shared utility modules.

Provides environment validation, email attachment validation,
log formatting, and task execution wrapper utilities.
"""

from tj_utils.format_log import format_log
from tj_utils.task_runner import (
    TaskResult,
    calculate_elapsed_time,
    check_lock_file,
    create_lock_file,
    format_task_failure_log,
    format_task_overlap_log,
    format_task_success_log,
    format_task_timeout_log,
    parse_lock_start_time,
    remove_lock_file,
    truncate_stderr,
)
from tj_utils.validate_attachment import (
    AttachmentValidationResult,
    MessageValidationResult,
    format_rejection_log,
    format_size_rejection_log,
    validate_attachment,
    validate_message_size,
)
from tj_utils.validate_env import (
    EnvValidationResult,
    TJEnvironment,
    validate_env,
    validate_log_level,
    validate_port,
    validate_required_vars,
    validate_timezone,
)

__all__ = [
    "AttachmentValidationResult",
    "EnvValidationResult",
    "MessageValidationResult",
    "TJEnvironment",
    "TaskResult",
    "calculate_elapsed_time",
    "check_lock_file",
    "create_lock_file",
    "format_log",
    "format_rejection_log",
    "format_size_rejection_log",
    "format_task_failure_log",
    "format_task_overlap_log",
    "format_task_success_log",
    "format_task_timeout_log",
    "parse_lock_start_time",
    "remove_lock_file",
    "truncate_stderr",
    "validate_attachment",
    "validate_env",
    "validate_log_level",
    "validate_message_size",
    "validate_port",
    "validate_required_vars",
    "validate_timezone",
]
