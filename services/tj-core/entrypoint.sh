#!/bin/bash
set -euo pipefail

SERVICE_NAME="tj-core"

# Source shared defaults — provides sensible values when .env is absent
if [ -f /app/shared/validate-env.sh ]; then
    source /app/shared/validate-env.sh
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Validate TJ_PROJECT_FILE environment variable is set and non-empty
if [ -z "${TJ_PROJECT_FILE:-}" ]; then
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] TJ_PROJECT_FILE environment variable is not set or empty"
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] Set TJ_PROJECT_FILE to the main project file name (e.g., project.tjp)"
    exit 1
fi

# Verify the project file exists in the project volume
PROJECT_PATH="/app/project/${TJ_PROJECT_FILE}"
if [ ! -f "$PROJECT_PATH" ]; then
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] Project file not found: $PROJECT_PATH"
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] Ensure the project volume is mounted and contains '$TJ_PROJECT_FILE'"
    exit 1
fi

echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Project file validated: $PROJECT_PATH"
echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Container ready, awaiting exec triggers"

# Keep container alive awaiting exec triggers
exec tail -f /dev/null
