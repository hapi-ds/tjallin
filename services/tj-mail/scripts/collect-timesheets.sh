#!/bin/bash
# collect-timesheets.sh — Flush pending emails and ensure all valid timesheets are stored
#
# This script is triggered by the Cron Service (or manually via scripts/collect-timesheets.sh)
# to process any pending emails in the Postfix mail queue. The actual email processing
# and timesheet extraction is handled by process-email.sh via the Postfix pipe transport.
#
# Exit codes:
#   0 — Success (queue flushed, all pending mail processed)
#
# Requirements: 5.4, 6.3

set -euo pipefail

SERVICE_NAME="tj-mail"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- Log helper using shared format ---
log_info() {
    echo "[$SERVICE_NAME] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [INFO] $1"
}

log_error() {
    echo "[$SERVICE_NAME] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [ERROR] $1" >&2
}

# --- Flush the Postfix mail queue to process pending emails ---
log_info "Starting timesheet collection: flushing mail queue"

if postfix flush 2>/dev/null; then
    log_info "Timesheet collection completed: mail queue flushed successfully"
else
    log_error "Failed to flush Postfix mail queue"
    exit 1
fi

exit 0
