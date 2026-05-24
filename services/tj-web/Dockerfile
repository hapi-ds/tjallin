FROM python:3.11-slim

# Install tj3 for compilation (Ruby + taskjuggler gem) and curl for health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ruby curl && gem install taskjuggler --no-document && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy project files needed for build
COPY pyproject.toml uv.lock README.md /app/
COPY src/ /app/src/
WORKDIR /app

# Install all dependencies and the project package
RUN uv sync --frozen --no-dev

# Bundle TaskJuggler reference documentation for offline availability
COPY docs/tj-reference/ /app/tj-docs/

EXPOSE 8080
CMD ["uv", "run", "tj-web"]
