FROM alpine:3.19

# Install bash, Docker CLI, timezone data, and procps (for pgrep health check)
RUN apk add --no-cache \
      bash \
      curl \
      docker-cli \
      tzdata \
      procps

# Install Supercronic (cron replacement designed for containers)
# Supercronic logs to stdout, handles signals properly, and doesn't need syslog
ARG SUPERCRONIC_VERSION=v0.2.29
ARG SUPERCRONIC_SHA256=cd48d45c4b10f3f0bfdd3a57d054cd05ac96812b

RUN curl -fsSL "https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64" \
      -o /usr/local/bin/supercronic && \
    chmod +x /usr/local/bin/supercronic

# Create application directories
RUN mkdir -p /app/scripts

# Copy entrypoint and scripts
COPY entrypoint.sh /app/entrypoint.sh
COPY scripts/ /app/scripts/
RUN chmod +x /app/entrypoint.sh /app/scripts/*.sh 2>/dev/null || true

# Health check: verify supercronic process is running
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD pgrep supercronic || exit 1

WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
