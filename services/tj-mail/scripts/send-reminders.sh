#!/bin/bash
# send-reminders.sh — Send timesheet reminder emails to configured recipients
#
# This script is triggered by the Cron Service (or manually via scripts/send-reminders.sh)
# to send timesheet submission reminders using the configured sender address.
#
# Exit codes:
#   0 — Success (reminder email sent)
#
# Requirements: 5.5, 6.4

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

# --- Determine sender address ---
SENDER="${TJ_MAIL_SENDER:-taskjuggler@${TJ_MAIL_DOMAIN:-taskjuggler.local}}"
DOMAIN="${TJ_MAIL_DOMAIN:-taskjuggler.local}"

# --- Send reminder email ---
log_info "Sending timesheet reminder from $SENDER"

SUBJECT="Timesheet Reminder - Please submit your timesheet"
BODY="This is a reminder to submit your timesheet for the current reporting period.

Please send your completed timesheet (.tji file) as an email attachment to:
  timesheets@${DOMAIN}

Or submit it through the web interface.

Thank you,
TaskJuggler System"

# Use sendmail (provided by Postfix) to send the reminder
if echo -e "From: ${SENDER}\nTo: timesheets@${DOMAIN}\nSubject: ${SUBJECT}\n\n${BODY}" | sendmail -f "$SENDER" "timesheets@${DOMAIN}"; then
    log_info "Timesheet reminder sent successfully from $SENDER"
else
    log_error "Failed to send timesheet reminder"
    exit 1
fi

exit 0
