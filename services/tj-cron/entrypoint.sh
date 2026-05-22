#!/bin/bash
set -euo pipefail

SERVICE_NAME="tj-cron"

# Source shared defaults — provides sensible values when .env is absent
if [ -f /app/shared/validate-env.sh ]; then
    source /app/shared/validate-env.sh
fi

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# --- Validate Docker socket access ---

DOCKER_SOCKET="/var/run/docker.sock"

if [ ! -S "$DOCKER_SOCKET" ]; then
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] Docker socket not found at $DOCKER_SOCKET"
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] Mount the Docker socket: -v /var/run/docker.sock:/var/run/docker.sock:ro"
    exit 1
fi

# Verify we can actually communicate with Docker
if ! docker info >/dev/null 2>&1; then
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] Cannot communicate with Docker daemon via $DOCKER_SOCKET"
    echo "[$SERVICE_NAME] [$TIMESTAMP] [ERROR] Check socket permissions and Docker daemon status"
    exit 1
fi

echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Docker socket validated: $DOCKER_SOCKET"

# --- Set timezone ---

TJ_TIMEZONE="${TJ_TIMEZONE:-UTC}"

if [ -f "/usr/share/zoneinfo/${TJ_TIMEZONE}" ]; then
    cp "/usr/share/zoneinfo/${TJ_TIMEZONE}" /etc/localtime
    echo "$TJ_TIMEZONE" > /etc/timezone
    echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Timezone set to: $TJ_TIMEZONE"
else
    echo "[$SERVICE_NAME] [$TIMESTAMP] [WARNING] Invalid timezone '$TJ_TIMEZONE', falling back to UTC"
    cp /usr/share/zoneinfo/UTC /etc/localtime
    echo "UTC" > /etc/timezone
fi

# --- Generate crontab from environment variables ---

TJ_CRON_COMPILE="${TJ_CRON_COMPILE:-*/15 * * * *}"
TJ_CRON_TIMESHEETS="${TJ_CRON_TIMESHEETS:-0 * * * *}"
TJ_CRON_REMINDERS="${TJ_CRON_REMINDERS:-0 9 * * 1}"

CRONTAB_FILE="/app/crontab"

cat > "$CRONTAB_FILE" <<EOF
# TaskJuggler Cron Schedule
# Generated at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Timezone: ${TJ_TIMEZONE}

# Project compilation
${TJ_CRON_COMPILE} /app/scripts/run-task.sh compile docker exec tj-core /app/scripts/compile.sh

# Timesheet collection
${TJ_CRON_TIMESHEETS} /app/scripts/run-task.sh timesheets docker exec tj-mail /app/scripts/collect-timesheets.sh

# Timesheet reminders
${TJ_CRON_REMINDERS} /app/scripts/run-task.sh reminders docker exec tj-mail /app/scripts/send-reminders.sh
EOF

echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Crontab generated at $CRONTAB_FILE"
echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Compile schedule: $TJ_CRON_COMPILE"
echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Timesheets schedule: $TJ_CRON_TIMESHEETS"
echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Reminders schedule: $TJ_CRON_REMINDERS"

# --- Start Supercronic ---

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "[$SERVICE_NAME] [$TIMESTAMP] [INFO] Starting Supercronic with crontab: $CRONTAB_FILE"

exec supercronic "$CRONTAB_FILE"
