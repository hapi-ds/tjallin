FROM alpine:3.19

# Install Postfix for MTA, Dovecot for IMAP, ripmime for MIME extraction, and utilities
# Note: maildrop is not available in Alpine 3.19; using Postfix pipe transport instead
# cyrus-sasl-plain/login are provided by cyrus-sasl package in Alpine 3.19
RUN apk add --no-cache \
      postfix \
      dovecot \
      python3 \
      bash \
      ca-certificates \
      cyrus-sasl \
      ripmime \
      coreutils

# Create application directories
RUN mkdir -p /app/timesheets /app/scripts /app/shared /etc/postfix /etc/dovecot

# Copy shared validation logic
COPY services/shared/validate-env.sh /app/shared/validate-env.sh

# Copy Dovecot configuration
COPY services/tj-mail/dovecot.conf /etc/dovecot/dovecot.conf

# Copy entrypoint and scripts
COPY services/tj-mail/entrypoint.sh /app/entrypoint.sh
COPY services/tj-mail/scripts/ /app/scripts/
RUN chmod +x /app/entrypoint.sh /app/scripts/*.sh /app/shared/validate-env.sh

# Expose SMTP and IMAP ports (internal only)
EXPOSE 25 143

# Health check: verify Postfix is running
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD postfix status || exit 1

WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
