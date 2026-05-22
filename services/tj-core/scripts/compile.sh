#!/bin/bash
set -euo pipefail

SERVICE_NAME="tj-core"
PROJECT_FILE="/app/project/${TJ_PROJECT_FILE:-project.tjp}"
REPORT_DIR="/app/reports"

# Log helper using shared format: [SERVICE_NAME] [ISO8601_TIMESTAMP] [LEVEL] message
log() {
    local level="$1"
    shift
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$SERVICE_NAME] [$timestamp] [$level] $*"
}

# Clear previous reports before writing new ones
rm -rf "${REPORT_DIR:?}"/*

# Run tj3 compilation
log "INFO" "Starting project compilation: $PROJECT_FILE"

if tj3_output=$(tj3 -o "$REPORT_DIR" "$PROJECT_FILE" 2>&1); then
    # Success: count generated reports and log
    report_count=$(find "$REPORT_DIR" -type f | wc -l)
    log "INFO" "Project compilation completed: $report_count reports generated"
    exit 0
else
    exit_code=$?
    # Failure: log full tj3 error output to stderr
    log "ERROR" "Project compilation failed with exit code $exit_code" >&2
    echo "$tj3_output" >&2
    exit $exit_code
fi
