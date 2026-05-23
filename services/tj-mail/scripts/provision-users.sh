#!/bin/bash
# provision-users.sh — Create mail user accounts and Dovecot passwd-file
#
# This script parses the TJ_MAIL_USERS environment variable (comma-separated
# user:password pairs) and provisions system accounts with Maildir directories.
# It also generates the Dovecot passwd-file for IMAP authentication.
#
# If TJ_MAIL_USERS is empty or unset, a single default account is created
# using the local-part of TJ_MAIL_SENDER as both username and password.
#
# Exit codes:
#   0 — Success (at least one user provisioned)
#   1 — Fatal error (no users could be provisioned)
#
# Requirements: 3.1, 3.2, 3.3, 3.4, 3.5

set -uo pipefail

SERVICE_NAME="tj-mail"
PASSWD_FILE="/etc/dovecot/users"
MAIL_BASE="/var/mail"
MAX_ENTRIES=50

# --- Log helpers using shared format ---
log_info() {
    echo "[$SERVICE_NAME] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [INFO] $1"
}

log_error() {
    echo "[$SERVICE_NAME] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [ERROR] $1" >&2
}

# --- Validation helpers ---
validate_username() {
    local username="$1"
    # Username: 1-64 characters, alphanumeric plus -_.
    if [ -z "$username" ] || [ ${#username} -gt 64 ]; then
        return 1
    fi
    if ! echo "$username" | grep -qE '^[a-zA-Z0-9._-]+$'; then
        return 1
    fi
    return 0
}

validate_password() {
    local password="$1"
    # Password: 1-128 characters, no commas or colons
    if [ -z "$password" ] || [ ${#password} -gt 128 ]; then
        return 1
    fi
    if echo "$password" | grep -qE '[,:]'; then
        return 1
    fi
    return 0
}

# --- Create a single user account with Maildir ---
provision_user() {
    local username="$1"
    local password="$2"
    local user_mail_dir="${MAIL_BASE}/${username}/Maildir"

    # Create system user if it doesn't already exist
    if ! id "$username" >/dev/null 2>&1; then
        adduser -D -h "${MAIL_BASE}/${username}" -s /sbin/nologin "$username" 2>/dev/null
        if [ $? -ne 0 ]; then
            log_error "Failed to create system user: $username"
            return 1
        fi
    fi

    # Create Maildir structure
    mkdir -p "${user_mail_dir}/new" "${user_mail_dir}/cur" "${user_mail_dir}/tmp"
    chown -R "$username:$username" "${MAIL_BASE}/${username}"
    chmod -R 700 "${MAIL_BASE}/${username}"

    # Get uid and gid for the user
    local uid gid
    uid=$(id -u "$username")
    gid=$(id -g "$username")

    # Append Dovecot passwd-file entry
    echo "${username}:{PLAIN}${password}:${uid}:${gid}::${MAIL_BASE}/${username}::" >> "$PASSWD_FILE"

    log_info "Provisioned user: $username (uid=$uid, gid=$gid)"
    return 0
}

# --- Main ---

# Ensure Dovecot config directory exists and start with empty passwd-file
mkdir -p "$(dirname "$PASSWD_FILE")"
: > "$PASSWD_FILE"
chmod 600 "$PASSWD_FILE"

PROVISIONED=0

if [ -z "${TJ_MAIL_USERS:-}" ]; then
    # Fallback: create default user from TJ_MAIL_SENDER local-part
    SENDER="${TJ_MAIL_SENDER:-taskjuggler@taskjuggler.local}"
    DEFAULT_USER="${SENDER%%@*}"

    if [ -z "$DEFAULT_USER" ]; then
        DEFAULT_USER="taskjuggler"
    fi

    log_info "TJ_MAIL_USERS not set, creating default user from TJ_MAIL_SENDER: $DEFAULT_USER"

    if provision_user "$DEFAULT_USER" "$DEFAULT_USER"; then
        PROVISIONED=1
    else
        log_error "Failed to provision default user: $DEFAULT_USER"
        exit 1
    fi
else
    # Parse comma-separated user:password pairs
    IFS=',' read -ra ENTRIES <<< "$TJ_MAIL_USERS"
    ENTRY_COUNT=${#ENTRIES[@]}

    if [ "$ENTRY_COUNT" -gt "$MAX_ENTRIES" ]; then
        log_error "TJ_MAIL_USERS contains $ENTRY_COUNT entries, maximum is $MAX_ENTRIES"
        # Process only the first MAX_ENTRIES
        ENTRY_COUNT=$MAX_ENTRIES
    fi

    for i in $(seq 0 $((ENTRY_COUNT - 1))); do
        ENTRY="${ENTRIES[$i]}"

        # Trim whitespace
        ENTRY=$(echo "$ENTRY" | xargs)

        # Skip empty entries
        if [ -z "$ENTRY" ]; then
            continue
        fi

        # Split on first colon only
        USERNAME="${ENTRY%%:*}"
        REST="${ENTRY#*:}"

        # Check that entry contains a colon (user:password format)
        if [ "$USERNAME" = "$ENTRY" ]; then
            log_error "Malformed entry (missing colon): '$ENTRY'"
            continue
        fi

        PASSWORD="$REST"

        # Validate username
        if ! validate_username "$USERNAME"; then
            log_error "Malformed entry (invalid username): '$ENTRY'"
            continue
        fi

        # Validate password
        if ! validate_password "$PASSWORD"; then
            log_error "Malformed entry (invalid password): '$ENTRY'"
            continue
        fi

        # Provision the user
        if provision_user "$USERNAME" "$PASSWORD"; then
            PROVISIONED=$((PROVISIONED + 1))
        fi
    done
fi

# Final status
if [ "$PROVISIONED" -eq 0 ]; then
    log_error "No users were provisioned"
    exit 1
fi

chmod 600 "$PASSWD_FILE"
log_info "User provisioning complete: $PROVISIONED user(s) configured"
exit 0
