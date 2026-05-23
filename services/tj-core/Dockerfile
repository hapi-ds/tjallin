FROM ruby:3.2-slim

# Install build dependencies for native gem extensions and Python 3 for post-processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      build-essential \
      python3 \
      && rm -rf /var/lib/apt/lists/*

# Install TaskJuggler gem
RUN gem install taskjuggler --no-document

# Create application directories
RUN mkdir -p /app/project /app/reports /app/timesheets /app/scripts /app/shared

# Copy shared validation logic
COPY services/shared/validate-env.sh /app/shared/validate-env.sh

# Copy Python post-processing utilities
COPY src/tj_utils/ /app/src/tj_utils/
COPY src/tj_utils/report_postprocess.py /app/src/report_postprocess.py

# Copy entrypoint and scripts
COPY services/tj-core/entrypoint.sh /app/entrypoint.sh
COPY services/tj-core/scripts/ /app/scripts/
RUN chmod +x /app/entrypoint.sh /app/scripts/*.sh /app/shared/validate-env.sh

# Health check: verify tj3 is installed and working
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD tj3 --version || exit 1

WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
