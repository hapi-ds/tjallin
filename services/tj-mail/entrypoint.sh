#!/bin/bash
set -euo pipefail

SERVICE_NAME="tj-mail"

# --- Log helpers ---
log_info() {
    echo "[$SERVICE_NAME] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [INFO] $1"
}

log_error() {
    echo "[$SERVICE_NAME] [$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [ERROR] $1" >&2
}

# --- Step 1: Validate required environment variables ---

if [ -z "${TJ_MAIL_DOMAIN:-}" ]; then
    log_error "TJ_MAIL_DOMAIN is required but not set. Cannot start mail service."
    exit 1
fi

log_info "Starting mail service for domain: ${TJ_MAIL_DOMAIN}"

# --- Step 2: Provision mail users ---

log_info "Provisioning mail users..."
if [ -x /scripts/provision-users.sh ]; then
    /scripts/provision-users.sh
elif [ -x /app/scripts/provision-users.sh ]; then
    /app/scripts/provision-users.sh
else
    log_error "provision-users.sh not found"
    exit 1
fi

# --- Step 3: Configure Postfix for local-only delivery ---

log_info "Configuring Postfix for local delivery"

cat > /etc/postfix/main.cf <<EOF
# Basic host identity
myhostname = mail.${TJ_MAIL_DOMAIN}
mydomain = ${TJ_MAIL_DOMAIN}
myorigin = \$mydomain

# Accept mail for the local domain
mydestination = \$myhostname, localhost, ${TJ_MAIL_DOMAIN}

# Listen on all interfaces (container-internal)
inet_interfaces = all
inet_protocols = ipv4

# Local delivery to Maildir
local_transport = local
home_mailbox = Maildir/

# Message size limit: 5 MB
message_size_limit = 5242880
mailbox_size_limit = 0

# Network configuration - accept mail from Docker network
mynetworks = 127.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 10.0.0.0/8

# Reject mail to non-local domains (554)
smtpd_recipient_restrictions = reject_unauth_destination

# Queue configuration
queue_directory = /var/spool/postfix

# Logging to stdout
maillog_file = /dev/stdout
EOF

# --- Optional relay support ---

if [ -n "${TJ_SMTP_RELAY_HOST:-}" ]; then
    RELAY_PORT="${TJ_SMTP_RELAY_PORT:-25}"
    log_info "Configuring relay host: ${TJ_SMTP_RELAY_HOST}:${RELAY_PORT}"
    postconf -e "relayhost = [${TJ_SMTP_RELAY_HOST}]:${RELAY_PORT}"
else
    log_info "No relay host configured — local-only delivery"
    postconf -e "relayhost ="
fi

# --- Ensure Postfix spool directories exist ---

mkdir -p /var/spool/postfix
postfix set-permissions 2>/dev/null || true

# --- Step 4: Start Dovecot in background ---

log_info "Starting Dovecot IMAP server"
dovecot -c /etc/dovecot/dovecot.conf

# --- Step 5: Start Postfix in foreground ---

log_info "Starting Postfix SMTP server"
log_info "Mail domain: ${TJ_MAIL_DOMAIN}"
log_info "Listening on SMTP port 25, IMAP port 143"

exec postfix start-fg
