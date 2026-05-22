#!/bin/bash
# =============================================================================
# Shared environment validation and default initialization
# =============================================================================
# Source this script in service entrypoints to apply default values for
# environment variables when .env is not present. This enables the system
# to start out-of-the-box without manual configuration.
#
# Usage in entrypoint scripts:
#   source /app/shared/validate-env.sh
#
# Requirements: 2.3, 2.5, 2.6, 7.4
# =============================================================================

# --- Apply defaults for required variables ---
# These defaults enable local development without a .env file.
# In production, users should create a .env from .env.example.

export TJ_PROJECT_PATH="${TJ_PROJECT_PATH:-./project}"
export TJ_PROJECT_FILE="${TJ_PROJECT_FILE:-project.tjp}"
export TJ_WEB_PORT="${TJ_WEB_PORT:-8080}"
export TJ_MAIL_DOMAIN="${TJ_MAIL_DOMAIN:-taskjuggler.local}"
export TJ_SMTP_HOST="${TJ_SMTP_HOST:-localhost}"
export TJ_SMTP_PORT="${TJ_SMTP_PORT:-25}"
export TJ_SMTP_USER="${TJ_SMTP_USER:-}"
export TJ_SMTP_PASSWORD="${TJ_SMTP_PASSWORD:-}"
export TJ_MAIL_SENDER="${TJ_MAIL_SENDER:-taskjuggler@${TJ_MAIL_DOMAIN}}"
export TJ_CRON_COMPILE="${TJ_CRON_COMPILE:-*/15 * * * *}"
export TJ_CRON_TIMESHEETS="${TJ_CRON_TIMESHEETS:-0 * * * *}"
export TJ_CRON_REMINDERS="${TJ_CRON_REMINDERS:-0 9 * * 1}"
export TJ_TIMEZONE="${TJ_TIMEZONE:-UTC}"
export TJ_LOG_LEVEL="${TJ_LOG_LEVEL:-INFO}"
export TJ_TASK_TIMEOUT="${TJ_TASK_TIMEOUT:-300}"

# --- Validate log level with fallback ---

_VALID_LOG_LEVELS="DEBUG INFO WARNING ERROR"
_LOG_LEVEL_UPPER=$(echo "$TJ_LOG_LEVEL" | tr '[:lower:]' '[:upper:]')

if ! echo "$_VALID_LOG_LEVELS" | grep -qw "$_LOG_LEVEL_UPPER"; then
    echo "[validate-env] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [WARNING] Invalid TJ_LOG_LEVEL '${TJ_LOG_LEVEL}', falling back to INFO"
    export TJ_LOG_LEVEL="INFO"
else
    export TJ_LOG_LEVEL="$_LOG_LEVEL_UPPER"
fi

# --- Validate port number ---

if [ -n "$TJ_WEB_PORT" ]; then
    if ! echo "$TJ_WEB_PORT" | grep -qE '^[0-9]+$'; then
        echo "[validate-env] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [ERROR] TJ_WEB_PORT must be a number, got: '${TJ_WEB_PORT}'"
        exit 1
    fi
    if [ "$TJ_WEB_PORT" -lt 1 ] || [ "$TJ_WEB_PORT" -gt 65535 ]; then
        echo "[validate-env] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [ERROR] TJ_WEB_PORT must be between 1 and 65535, got: ${TJ_WEB_PORT}"
        exit 1
    fi
fi

# --- Volume initialization ---
# Docker named volumes are initialized automatically on first start.
# Bind mounts (TJ_PROJECT_PATH) must exist on the host.
# Entrypoint scripts handle creating subdirectories within volumes
# (e.g., /app/timesheets, /app/reports) ensuring first-time startup
# works without manual intervention.
# Subsequent starts reuse existing volumes without re-initialization
# because Docker preserves named volume contents across restarts.
