#!/bin/bash
set -euo pipefail

SERVICE_NAME="tj-mail"
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- Validate required environment variables ---

MISSING_VARS=""

if [ -z "${TJ_MAIL_DOMAIN:-}" ]; then
    MISSING_VARS="${MISSING_VARS} TJ_MAIL_DOMAIN"
fi

if [ -z "${TJ_SMTP_HOST:-}" ]; then
    MISSING_VARS="${MISSING_VARS} TJ_SMTP_HOST"
fi

if [ -z "${TJ_SMTP_PORT:-}" ]; then
    MISSING_VARS="${MISSING_VARS} TJ_SMTP_PORT"
fi

if [ -n "$MISSING_VARS" ]; then
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] Missing required environment variables:${MISSING_VARS}"
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] Set these variables in your .env file before starting the mail service"
    exit 1
fi

echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Configuring Postfix for domain: ${TJ_MAIL_DOMAIN}"

# --- Configure Postfix main.cf ---

cat > /etc/postfix/main.cf <<EOF
# Basic configuration
myhostname = mail.${TJ_MAIL_DOMAIN}
mydomain = ${TJ_MAIL_DOMAIN}
myorigin = \$mydomain
mydestination = \$myhostname, \$mydomain, localhost.\$mydomain, localhost
inet_interfaces = all
inet_protocols = ipv4

# Mailbox configuration
home_mailbox = Maildir/
mailbox_size_limit = 0
message_size_limit = 5242880

# Local delivery via pipe transport (configured below)
local_transport = timesheet

# Network configuration - accept mail from Docker network
mynetworks = 127.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, 10.0.0.0/8

# SMTP relay configuration for outbound mail
relayhost = [${TJ_SMTP_HOST}]:${TJ_SMTP_PORT}

# SMTP authentication for relay
smtp_sasl_auth_enable = yes
smtp_sasl_password_maps = hash:/etc/postfix/sasl_passwd
smtp_sasl_security_options = noanonymous
smtp_tls_security_level = encrypt
smtp_tls_CAfile = /etc/ssl/certs/ca-certificates.crt

# Queue configuration
queue_directory = /var/spool/postfix

# Logging to stdout
maillog_file = /dev/stdout
EOF

# --- Set up SMTP relay credentials ---

SMTP_USER="${TJ_SMTP_USER:-}"
SMTP_PASSWORD="${TJ_SMTP_PASSWORD:-}"

if [ -n "$SMTP_USER" ] && [ -n "$SMTP_PASSWORD" ]; then
    echo "[${TJ_SMTP_HOST}]:${TJ_SMTP_PORT} ${SMTP_USER}:${SMTP_PASSWORD}" > /etc/postfix/sasl_passwd
    postmap /etc/postfix/sasl_passwd
    chmod 600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db
    echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] SMTP relay credentials configured for ${TJ_SMTP_HOST}:${TJ_SMTP_PORT}"
else
    # Create empty sasl_passwd to avoid Postfix errors
    touch /etc/postfix/sasl_passwd
    postmap /etc/postfix/sasl_passwd
    chmod 600 /etc/postfix/sasl_passwd /etc/postfix/sasl_passwd.db
    # Disable SASL auth if no credentials provided
    postconf -e "smtp_sasl_auth_enable = no"
    echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] No SMTP credentials provided, relay authentication disabled"
fi

# --- Configure local delivery for timesheet processing ---

# Set up Postfix pipe transport to route incoming mail through process-email.sh
# This replaces maildrop with a custom script that validates and stores .tji attachments

# Add the timesheet pipe transport to master.cf
cat >> /etc/postfix/master.cf <<EOF

# Timesheet processing pipe transport
timesheet unix  -       n       n       -       10      pipe
  flags=F user=nobody argv=/app/scripts/process-email.sh
EOF

# Configure Postfix to use the pipe transport for local delivery
postconf -e "mailbox_command ="

# Ensure timesheet directory exists and is writable
mkdir -p /app/timesheets
chmod 777 /app/timesheets

# --- Ensure Postfix spool directories exist ---

mkdir -p /var/spool/postfix
postfix set-permissions 2>/dev/null || true

# --- Start Postfix in foreground mode ---

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Starting Postfix mail service"
echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Mail domain: ${TJ_MAIL_DOMAIN}"
echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] SMTP relay: ${TJ_SMTP_HOST}:${TJ_SMTP_PORT}"
echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Listening on port 25 (internal)"

# Start Postfix in foreground (daemon mode with stdout logging)
exec postfix start-fg
