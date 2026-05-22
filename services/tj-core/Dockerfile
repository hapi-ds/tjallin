FROM ruby:3.2-slim

# Install build dependencies for native gem extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      && rm -rf /var/lib/apt/lists/*

# Install TaskJuggler gem
RUN gem install taskjuggler --no-document

# Create application directories
RUN mkdir -p /app/project /app/reports /app/timesheets /app/scripts

# Copy entrypoint and scripts
COPY entrypoint.sh /app/entrypoint.sh
COPY scripts/ /app/scripts/
RUN chmod +x /app/entrypoint.sh /app/scripts/*.sh

# Health check: verify tj3 is installed and working
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD tj3 --version || exit 1

WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
