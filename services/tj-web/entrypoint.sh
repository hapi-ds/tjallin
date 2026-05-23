#!/bin/bash
set -uo pipefail

SERVICE_NAME="tj-web"

# Source shared defaults — provides sensible values when .env is absent
if [ -f /app/shared/validate-env.sh ]; then
    source /app/shared/validate-env.sh
fi

MIN_RESTART_INTERVAL=30
REPORT_DIR="/app/reports"
STATIC_DIR="/app/static"
FALLBACK_PAGE="${STATIC_DIR}/no-reports.html"
FALLBACK_CHECK_INTERVAL=10
TJ3D_PID=""
FALLBACK_PID=""
SHUTDOWN=0

log() {
    local level="$1"
    shift
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$SERVICE_NAME] [$timestamp] [$level] $*"
}

# Check if report volume contains any report files
reports_exist() {
    # Look for HTML or CSV files in the report directory
    local count
    count=$(find "$REPORT_DIR" -maxdepth 1 -type f \( -name "*.html" -o -name "*.csv" \) 2>/dev/null | wc -l)
    [ "$count" -gt 0 ]
}

# Start a simple Ruby WEBrick server to serve the fallback page
start_fallback_server() {
    log "INFO" "No reports found in ${REPORT_DIR}, serving fallback status page"
    ruby -r webrick -e "
      server = WEBrick::HTTPServer.new(Port: 8080, DocumentRoot: '${STATIC_DIR}')
      server.mount_proc('/') do |req, res|
        res['Content-Type'] = 'text/html'
        res.body = File.read('${FALLBACK_PAGE}')
      end
      trap('INT') { server.shutdown }
      trap('TERM') { server.shutdown }
      server.start
    " &
    FALLBACK_PID=$!
    log "INFO" "Fallback server started on port 8080 (PID: ${FALLBACK_PID})"
}

# Stop the fallback server
stop_fallback_server() {
    if [ -n "$FALLBACK_PID" ] && kill -0 "$FALLBACK_PID" 2>/dev/null; then
        log "INFO" "Stopping fallback server (PID: ${FALLBACK_PID})"
        kill "$FALLBACK_PID" 2>/dev/null
        wait "$FALLBACK_PID" 2>/dev/null
        FALLBACK_PID=""
    fi
}

# Wait for reports to appear, then transition to normal operation
wait_for_reports() {
    while [ $SHUTDOWN -eq 0 ]; do
        if reports_exist; then
            log "INFO" "Reports detected in ${REPORT_DIR}, transitioning to normal operation"
            stop_fallback_server
            start_normal_operation
            return
        fi
        sleep "$FALLBACK_CHECK_INTERVAL"
    done
}

# Graceful shutdown handler
shutdown_handler() {
    SHUTDOWN=1
    log "INFO" "Shutting down processes..."

    stop_fallback_server

    if [ -n "${ADMIN_PID:-}" ] && kill -0 "$ADMIN_PID" 2>/dev/null; then
        kill "$ADMIN_PID" 2>/dev/null
        wait "$ADMIN_PID" 2>/dev/null
    fi

    if [ -n "$TJ3D_PID" ] && kill -0 "$TJ3D_PID" 2>/dev/null; then
        kill "$TJ3D_PID" 2>/dev/null
        wait "$TJ3D_PID" 2>/dev/null
    fi

    log "INFO" "All processes stopped"
    exit 0
}

trap shutdown_handler SIGTERM SIGINT SIGQUIT

# Start tj3d (TaskJuggler daemon) with restart supervision
start_tj3d() {
    # Serve generated reports via a simple WEBrick file server on port 8080
    while [ $SHUTDOWN -eq 0 ]; do
        local start_time
        start_time=$(date +%s)

        log "INFO" "Starting report web server on port 8080 (serving ${REPORT_DIR})..."
        ruby -r webrick -e "
          server = WEBrick::HTTPServer.new(
            Port: 8080,
            DocumentRoot: '${REPORT_DIR}',
            Logger: WEBrick::Log.new('/dev/null'),
            AccessLog: []
          )
          # Serve index listing if no index.html exists
          server.mount('/', WEBrick::HTTPServlet::FileHandler, '${REPORT_DIR}', FancyIndexing: true)
          trap('INT') { server.shutdown }
          trap('TERM') { server.shutdown }
          server.start
        " &
        TJ3D_PID=$!

        wait "$TJ3D_PID" 2>/dev/null
        local exit_code=$?
        TJ3D_PID=""

        if [ $SHUTDOWN -eq 1 ]; then
            break
        fi

        local end_time
        end_time=$(date +%s)
        local elapsed=$((end_time - start_time))

        if [ $elapsed -lt $MIN_RESTART_INTERVAL ]; then
            log "WARNING" "Report server exited after ${elapsed}s (exit code: $exit_code), restarting in 5s..."
            sleep 5
        else
            log "WARNING" "Report server exited after ${elapsed}s (exit code: $exit_code), restarting..."
        fi
    done
}

# Start normal tj3d operation (includes built-in web server)
start_normal_operation() {
    log "INFO" "Starting normal operation with tj3d (includes web server)"

    # Start tj3d with supervision
    start_tj3d &
    TJ3D_LOOP_PID=$!

    log "INFO" "Process supervision active for tj3d"

    # Wait for supervision loop to exit (shouldn't happen unless shutdown)
    wait "$TJ3D_LOOP_PID" 2>/dev/null

    # If we get here without shutdown signal, trigger shutdown
    if [ $SHUTDOWN -eq 0 ]; then
        log "ERROR" "Supervision loop exited unexpectedly, shutting down"
        shutdown_handler
    fi
}

# --- Main ---

log "INFO" "TJ Web Service starting"
log "INFO" "Report volume: ${REPORT_DIR}"
log "INFO" "Project volume: /app/project"

# Start admin panel on port 9090 (always available)
ruby /app/admin/server.rb &
ADMIN_PID=$!
log "INFO" "Admin panel started on port 9090"

# Check if reports exist; if not, serve fallback page until they appear
if reports_exist; then
    start_normal_operation
else
    start_fallback_server
    wait_for_reports
fi
