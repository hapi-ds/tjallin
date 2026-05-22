#!/bin/bash
set -uo pipefail

# Task execution wrapper for tj-cron scheduled tasks.
#
# Usage: /app/scripts/run-task.sh <task_name> <command...>
#
# Implements:
#   - Lock file mechanism to prevent overlapping executions
#   - Configurable timeout (TJ_TASK_TIMEOUT, default 300s)
#   - Structured logging: [tj-cron] [ISO8601] [LEVEL] message
#   - Stale lock file detection and cleanup
#   - Stderr capture with truncation to 1000 chars

SERVICE_NAME="tj-cron"
LOCK_DIR="/tmp"

# --- Argument parsing ---

if [ $# -lt 2 ]; then
    echo "[${SERVICE_NAME}] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [ERROR] Usage: run-task.sh <task_name> <command...>"
    exit 1
fi

TASK_NAME="$1"
shift
COMMAND=("$@")

LOCK_FILE="${LOCK_DIR}/tj-${TASK_NAME}.lock"
TIMEOUT="${TJ_TASK_TIMEOUT:-300}"

# --- Helper functions ---

log_info() {
    echo "[${SERVICE_NAME}] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [INFO] $1"
}

log_warning() {
    echo "[${SERVICE_NAME}] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [WARNING] $1"
}

log_error() {
    echo "[${SERVICE_NAME}] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [ERROR] $1"
}

cleanup() {
    rm -f "$LOCK_FILE"
}

# --- Lock file check ---

if [ -f "$LOCK_FILE" ]; then
    # Read lock file content (format: PID=<pid> STARTED=<iso8601>)
    LOCK_CONTENT=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
    LOCK_PID=$(echo "$LOCK_CONTENT" | sed -n 's/.*PID=\([0-9]*\).*/\1/p')

    if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
        # Process is still running — skip execution
        LOCK_STARTED=$(echo "$LOCK_CONTENT" | sed -n 's/.*STARTED=\([^ ]*\).*/\1/p')
        if [ -n "$LOCK_STARTED" ]; then
            START_EPOCH=$(date -d "$LOCK_STARTED" +%s 2>/dev/null || echo "0")
            NOW_EPOCH=$(date -u +%s)
            ELAPSED=$(( NOW_EPOCH - START_EPOCH ))
        else
            ELAPSED="unknown"
        fi
        log_warning "Task '${TASK_NAME}' skipped: previous execution still running (elapsed: ${ELAPSED}s)"
        exit 0
    else
        # Process is dead — stale lock file, remove and proceed
        log_warning "Removing stale lock file for task '${TASK_NAME}' (PID ${LOCK_PID} no longer running)"
        rm -f "$LOCK_FILE"
    fi
fi

# --- Create lock file ---

STARTED_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "PID=$$ STARTED=${STARTED_AT}" > "$LOCK_FILE"

# --- Trap-based cleanup (remove lock file on exit) ---

trap cleanup EXIT

# --- Execute command with timeout ---

STDERR_FILE=$(mktemp /tmp/tj-stderr-XXXXXX)

timeout "${TIMEOUT}" "${COMMAND[@]}" 2>"$STDERR_FILE"
EXIT_CODE=$?

# --- Handle results ---

if [ $EXIT_CODE -eq 0 ]; then
    # Success
    log_info "Task '${TASK_NAME}' completed successfully"
elif [ $EXIT_CODE -eq 124 ]; then
    # Timeout (exit code 124 from GNU timeout)
    log_error "Task '${TASK_NAME}' timed out after ${TIMEOUT}s"
else
    # Failure
    STDERR_CONTENT=$(head -c 1000 "$STDERR_FILE" 2>/dev/null || echo "")
    if [ -n "$STDERR_CONTENT" ]; then
        log_error "Task '${TASK_NAME}' failed: exit code ${EXIT_CODE}"
        echo "[${SERVICE_NAME}] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [ERROR] ${STDERR_CONTENT}"
    else
        log_error "Task '${TASK_NAME}' failed: exit code ${EXIT_CODE}"
    fi
fi

# --- Cleanup stderr temp file ---

rm -f "$STDERR_FILE"

exit $EXIT_CODE
