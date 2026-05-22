FROM alpine:3.19

# Install Postfix for MTA, maildrop for local delivery, ripmime for MIME extraction, and utilities
RUN apk add --no-cache \
      postfix \
      maildrop \
      bash \
      ca-certificates \
      cyrus-sasl \
      cyrus-sasl-plain \
      cyrus-sasl-login \
      mailx \
      ripmime \
      coreutils

# Create application directories
RUN mkdir -p /app/timesheets /app/scripts /etc/postfix

# Copy entrypoint and scripts
COPY entrypoint.sh /app/entrypoint.sh
COPY scripts/ /app/scripts/
RUN chmod +x /app/entrypoint.sh /app/scripts/*.sh

# Expose SMTP port (internal only)
EXPOSE 25

# Health check: verify Postfix is running
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD postfix status || exit 1

WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
