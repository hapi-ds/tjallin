#!/bin/bash
# process-email.sh — Inbound email processing pipeline for TaskJuggler timesheets
#
# This script is invoked by Postfix as a pipe transport. It reads an email
# from stdin, validates the message size and attachments, and copies valid
# .tji timesheet files to the shared timesheet volume.
#
# Exit codes:
#   0 — Success (at least one valid .tji attachment processed)
#   1 — Rejection (invalid email: oversized, no valid attachments, etc.)
#
# Requirements: 5.3, 5.7, 5.8, 5.9

set -uo pipefail

SERVICE_NAME="tj-mail"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TIMESHEET_DIR="/app/timesheets"
WORK_DIR=$(mktemp -d /tmp/email-process.XXXXXX)
MAX_MESSAGE_SIZE=5242880   # 5 MB in bytes
MAX_ATTACHMENT_SIZE=1048576 # 1 MB in bytes

# Cleanup temporary directory on exit
cleanup() {
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

# --- Log helper using shared format ---
log_info() {
    echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] $1"
}

log_warning() {
    echo "[$SERVICE_NAME] [$TIMESTAMP] [WARNING] $1"
}

log_error() {
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] $1" >&2
}

# --- Read email from stdin into a temporary file ---
EMAIL_FILE="$WORK_DIR/message.eml"
cat > "$EMAIL_FILE"

# --- Check total message size ---
MESSAGE_SIZE=$(stat -c %s "$EMAIL_FILE" 2>/dev/null || stat -f %z "$EMAIL_FILE" 2>/dev/null)

if [ -z "$MESSAGE_SIZE" ]; then
    log_error "Failed to determine message size"
    exit 1
fi

# --- Extract sender and subject for logging ---
SENDER=$(grep -m1 -i "^From:" "$EMAIL_FILE" | sed 's/^[Ff]rom:[[:space:]]*//' | head -1)
SENDER=${SENDER:-"unknown"}

SUBJECT=$(grep -m1 -i "^Subject:" "$EMAIL_FILE" | sed 's/^[Ss]ubject:[[:space:]]*//' | head -1)
SUBJECT=${SUBJECT:-"(no subject)"}

# --- Validate total message size (reject if > 5 MB) ---
if [ "$MESSAGE_SIZE" -gt "$MAX_MESSAGE_SIZE" ]; then
    SIZE_MB=$(awk "BEGIN {printf \"%.2f\", $MESSAGE_SIZE / 1048576}")
    log_warning "Rejected email from $SENDER: message size ${SIZE_MB} MB exceeds 5 MB limit"
    exit 1
fi

# --- Extract attachments using ripmime ---
# ripmime extracts MIME attachments from an email message
EXTRACT_DIR="$WORK_DIR/attachments"
mkdir -p "$EXTRACT_DIR"

if command -v ripmime >/dev/null 2>&1; then
    ripmime -i "$EMAIL_FILE" -d "$EXTRACT_DIR" --no-nameless 2>/dev/null
elif command -v munpack >/dev/null 2>&1; then
    (cd "$EXTRACT_DIR" && munpack -q "$EMAIL_FILE" 2>/dev/null)
else
    # Fallback: use a simple approach to extract base64-encoded attachments
    # This handles the most common case of single-part MIME attachments
    log_error "No MIME extraction tool available (ripmime or munpack required)"
    exit 1
fi

# --- Process extracted attachments ---
VALID_COUNT=0
REJECTED_COUNT=0

# Find all extracted files (skip textfile and other ripmime metadata)
for ATTACHMENT in "$EXTRACT_DIR"/*; do
    # Skip if no files found (glob didn't match)
    [ -e "$ATTACHMENT" ] || continue

    FILENAME=$(basename "$ATTACHMENT")

    # Skip ripmime metadata files
    case "$FILENAME" in
        textfile*|htmlfile*) continue ;;
    esac

    # Check .tji extension (case-insensitive)
    if ! echo "$FILENAME" | grep -qi '\.tji$'; then
        log_warning "Rejected email from $SENDER (subject: '$SUBJECT'): attachment '$FILENAME' does not have required .tji extension"
        REJECTED_COUNT=$((REJECTED_COUNT + 1))
        continue
    fi

    # Check attachment size (≤ 1 MB)
    ATTACH_SIZE=$(stat -c %s "$ATTACHMENT" 2>/dev/null || stat -f %z "$ATTACHMENT" 2>/dev/null)

    if [ -z "$ATTACH_SIZE" ]; then
        log_warning "Rejected email from $SENDER (subject: '$SUBJECT'): could not determine size of attachment '$FILENAME'"
        REJECTED_COUNT=$((REJECTED_COUNT + 1))
        continue
    fi

    if [ "$ATTACH_SIZE" -gt "$MAX_ATTACHMENT_SIZE" ]; then
        SIZE_MB=$(awk "BEGIN {printf \"%.2f\", $ATTACH_SIZE / 1048576}")
        log_warning "Rejected email from $SENDER (subject: '$SUBJECT'): attachment '$FILENAME' exceeds 1 MB size limit (size: ${SIZE_MB} MB)"
        REJECTED_COUNT=$((REJECTED_COUNT + 1))
        continue
    fi

    # --- Copy valid .tji attachment to timesheet volume ---
    if cp "$ATTACHMENT" "$TIMESHEET_DIR/$FILENAME"; then
        log_info "Stored timesheet '$FILENAME' from $SENDER (size: $ATTACH_SIZE bytes)"
        VALID_COUNT=$((VALID_COUNT + 1))
    else
        log_error "Failed to copy attachment '$FILENAME' to $TIMESHEET_DIR"
        REJECTED_COUNT=$((REJECTED_COUNT + 1))
    fi
done

# --- Final status ---
if [ "$VALID_COUNT" -eq 0 ]; then
    if [ "$REJECTED_COUNT" -gt 0 ]; then
        log_warning "Rejected email from $SENDER (subject: '$SUBJECT'): no valid .tji attachments found ($REJECTED_COUNT attachment(s) rejected)"
    else
        log_warning "Rejected email from $SENDER (subject: '$SUBJECT'): no attachments found"
    fi
    exit 1
fi

log_info "Processed email from $SENDER: $VALID_COUNT timesheet(s) stored"
exit 0
