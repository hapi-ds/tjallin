FROM ruby:3.2-slim

# Install build dependencies for native gem extensions and curl for health checks
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      curl \
      && rm -rf /var/lib/apt/lists/*

# Install TaskJuggler gem (provides tj3d and tj3webd)
RUN gem install taskjuggler --no-document

# Create application directories
RUN mkdir -p /app/project /app/reports /app/static

# Copy entrypoint and static files
COPY entrypoint.sh /app/entrypoint.sh
COPY static/ /app/static/
RUN chmod +x /app/entrypoint.sh

# Health check: verify web interface is responding
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD curl -f http://localhost:8080/ || exit 1

WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
