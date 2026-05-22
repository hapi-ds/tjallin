#!/usr/bin/env bash
set -euo pipefail

# Manual trigger script: Timesheet collection
#
# Triggers the same timesheet collection operation as the Cron Service
# scheduled timesheet collection task by executing collect-timesheets.sh
# inside the tj-mail container via docker exec.
#
# Requirements: 10.2, 10.4, 10.5, 10.6

CONTAINER="tj-mail"
LOCK_FILE="/tmp/tj-timesheets.lock"
SCRIPT="/app/scripts/collect-timesheets.sh"

# --- Color codes ---
BLUE='\033[34m'
GREEN='\033[32m'
RED='\033[31m'
YELLOW='\033[33m'
RESET='\033[0m'

# --- Check Docker CLI is available ---
if ! command -v docker &>/dev/null; then
    echo -e "${RED}✗ Docker CLI is not available.${RESET}"
    echo "  Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# --- Check container is running ---
if ! docker inspect --format='{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true; then
    echo -e "${RED}✗ Container '$CONTAINER' is not running.${RESET}"
    echo "  Start the stack with: docker compose up -d"
    exit 1
fi

# --- Check lock file (same mechanism as cron task wrapper) ---
if docker exec "$CONTAINER" test -f "$LOCK_FILE" 2>/dev/null; then
    STARTED=$(docker exec "$CONTAINER" cat "$LOCK_FILE" 2>/dev/null || echo "unknown")
    echo -e "${YELLOW}⚠ Operation already in progress (lock file exists).${RESET}"
    echo "  Lock info: $STARTED"
    echo "  If this is stale, remove it with: docker exec $CONTAINER rm $LOCK_FILE"
    exit 1
fi

# --- Execute timesheet collection ---
echo -e "${BLUE}→ Triggering timesheet collection...${RESET}"
if docker exec "$CONTAINER" "$SCRIPT"; then
    echo -e "${GREEN}✓ Timesheet collection completed successfully.${RESET}"
else
    EXIT_CODE=$?
    echo -e "${RED}✗ Timesheet collection failed (exit code: $EXIT_CODE).${RESET}"
    exit $EXIT_CODE
fi
