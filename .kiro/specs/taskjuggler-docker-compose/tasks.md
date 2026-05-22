# Implementation Plan: TaskJuggler Docker Compose

## Overview

This plan implements a multi-container Docker Compose system for TaskJuggler with four services (core, web, mail, cron), shared volumes, environment-based configuration, a comprehensive sample project demonstrating advanced TaskJuggler features, manual trigger scripts for on-demand operations, comprehensive documentation, and a full test suite. Tasks are ordered to build foundational infrastructure first, then layer services, wire everything together with orchestration, add manual trigger scripts, and finally produce documentation and testing.

## Tasks

- [ ] 1. Set up project structure and shared utilities
  - [-] 1.1 Create directory structure and configuration files
    - Create `services/tj-core/`, `services/tj-web/`, `services/tj-mail/`, `services/tj-cron/` directories
    - Create `project/` and `project/includes/` and `project/timesheets/` directories
    - Create `scripts/` directory for host-side manual trigger scripts
    - Create `docs/` directory for user guide documentation
    - Create `tests/unit/`, `tests/property/`, `tests/integration/`, `tests/e2e/` directories
    - Create `src/` directory for shared Python utility modules
    - Initialize Python project with `pyproject.toml` using uv, adding pytest and hypothesis as dev dependencies
    - Create `.env.example` with all configurable parameters, default values, and descriptive comments
    - _Requirements: 1.1, 2.2, 7.1, 7.3, 9.6_

  - [~] 1.2 Implement shared Python utility modules
    - Create `src/tj_utils/validate_env.py` — environment variable validation logic (required vars check, port validation, log level validation, timezone validation)
    - Create `src/tj_utils/validate_attachment.py` — email attachment validation (`.tji` extension check, size ≤ 1 MB, total message size ≤ 5 MB)
    - Create `src/tj_utils/format_log.py` — log line formatting function producing `[SERVICE_NAME] [ISO8601_TIMESTAMP] [LEVEL] message`
    - Create `src/tj_utils/task_runner.py` — task execution wrapper logic (lock file check, timeout handling, stderr truncation to 1000 chars, overlap detection)
    - Use Pydantic for environment variable validation models
    - _Requirements: 2.5, 2.6, 5.7, 5.8, 5.9, 6.5, 6.7, 8.2, 8.4_

  - [~] 1.3 Create comprehensive sample project — main file and accounts
    - Create `project/project.tjp` — main project file defining project header (name: "Acme Web Platform", start: 2024-01-15, duration: +16w, timezone: Europe/Stockholm, currency: SEK, trackingscenario: plan) and include directives for all modular files
    - Create `project/includes/accounts.tji` — cost account hierarchy (cost → dev → backend/frontend, design, qa, mgmt; revenue → contract) for financial tracking
    - _Requirements: 9.6, 9.7, 9.8_

  - [~] 1.4 Create sample project — resource definitions
    - Create `project/includes/resources.tji` — define five resources:
      - Alice: Senior Developer, 8h/day Mon–Fri, 950 SEK/h, skills: backend/architecture, vacation 2024-02-19 – 2024-02-23
      - Bob: Full-Stack Developer, 8h/day Mon–Fri, 800 SEK/h, skills: frontend/backend, vacation 2024-03-25 – 2024-03-29
      - Carol: UX Designer, 6h/day Mon–Thu, 750 SEK/h, skills: design/frontend, no vacation
      - Dave: QA Engineer, 8h/day Mon–Fri, 700 SEK/h, skills: testing/automation, vacation 2024-04-01 – 2024-04-05
      - Eve: Project Manager, 4h/day Mon–Fri, 900 SEK/h, skills: management, no vacation
    - Use `workinghours`, `vacation`, `limits`, and custom resource attributes for skill sets
    - Assign each resource to appropriate cost accounts with their hourly rates
    - _Requirements: 9.1, 9.7_

  - [~] 1.5 Create sample project — task hierarchy with dependencies and milestones
    - Create `project/includes/tasks.tji` — four-phase hierarchical task structure:
      - Phase 1: Planning (2 weeks) — Requirements gathering [Eve, Alice], Architecture design [Alice], UX wireframes [Carol], Milestone: Planning Complete
      - Phase 2: Development (6 weeks) — Backend API (Database schema [Alice], REST endpoints [Alice, Bob], Authentication [Alice]), Frontend UI (Component library [Bob, Carol], Page layouts [Bob], API integration [Bob]), Milestone: Feature Complete
      - Phase 3: Testing (4 weeks) — Unit test suite [Dave], Integration testing [Dave, Bob], Performance testing [Dave], UAT [Eve, Carol], Milestone: Release Candidate
      - Phase 4: Deployment (2 weeks) — Infrastructure setup [Alice], Staging deployment [Alice, Dave], Production deployment [Alice], Milestone: Go Live
    - Define explicit `depends` relationships between tasks (Architecture depends on Requirements, Phase 2 depends on Planning Complete milestone, API integration depends on REST endpoints, Integration testing depends on Feature Complete, Production deployment depends on Release Candidate)
    - Allocate Alice to overlapping tasks (REST endpoints + Authentication) and Bob to concurrent tasks (Component library + Page layouts) to demonstrate resource leveling
    - Assign each task to appropriate cost accounts
    - _Requirements: 9.2, 9.3, 9.7, 9.8_

  - [~] 1.6 Create sample project — report definitions
    - Create `project/includes/reports.tji` — four report types:
      - `GanttChart`: taskreport with full project Gantt chart, dependencies, milestones, critical path highlighted
      - `ResourceUsage`: resourcereport showing allocation over time, utilization percentages, conflicts
      - `TaskList`: taskreport in list format with start/end dates, effort, cost, completion status
      - `CostReport`: accountreport with financial breakdown by cost account (planned vs. actual)
    - Configure appropriate columns, time scales, and filters for each report
    - _Requirements: 9.4_

  - [~] 1.7 Create sample project — timesheet files
    - Create `project/timesheets/2024-W03-alice.tji` — Alice's timesheet for week 3 (work on database schema and REST endpoints)
    - Create `project/timesheets/2024-W03-bob.tji` — Bob's timesheet for week 3 (work on component library)
    - Create `project/timesheets/2024-W04-alice.tji` — Alice's timesheet for week 4 (continued REST endpoints and authentication)
    - Create `project/timesheets/2024-W04-bob.tji` — Bob's timesheet for week 4 (page layouts and API integration start)
    - Each timesheet uses proper TaskJuggler timesheet syntax with task references, work hours, and status annotations
    - _Requirements: 9.5_

  - [~] 1.8 Create sample project documentation
    - Create `project/README.md` covering:
      - Project overview and what the sample demonstrates
      - File-by-file explanation of each include file's purpose
      - How to modify the sample (add resources, tasks, change dates)
      - How timesheets work and how to submit them
      - How to create a new project from scratch using this structure as a template
      - Links to TaskJuggler documentation for each feature demonstrated
    - _Requirements: 9.10_

  - [~] 1.9 Write property tests for environment validation (Property 1)
    - **Property 1: Environment validation rejects missing required variables with descriptive error**
    - Test with random dicts where required keys (`TJ_SMTP_HOST`, `TJ_SMTP_PORT`, `TJ_MAIL_DOMAIN`) are present/absent/empty
    - Verify failure result contains names of all missing/empty required variables
    - Use `@settings(max_examples=100)` minimum
    - **Validates: Requirements 2.5, 2.6**

  - [~] 1.10 Write property tests for email attachment validation (Property 2)
    - **Property 2: Email attachment validation accepts only .tji files within size limit**
    - Test with random filenames (with/without `.tji`) × random sizes (0–2 MB)
    - Verify acceptance iff filename ends with `.tji` AND size ≤ 1 MB
    - Verify rejection log contains sender address, subject line, and reason
    - Use `@settings(max_examples=100)` minimum
    - **Validates: Requirements 5.7, 5.8**

  - [~] 1.11 Write property tests for oversized email rejection (Property 3)
    - **Property 3: Oversized email rejection**
    - Test with random email sizes (1 MB–10 MB), verify rejection for sizes > 5 MB
    - Verify rejection log contains sender address and message size
    - Use `@settings(max_examples=100)` minimum
    - **Validates: Requirements 5.9**

  - [~] 1.12 Write property tests for log formatting (Property 4)
    - **Property 4: Log entry format includes service name and ISO 8601 timestamp**
    - Test with random service names × random message strings (including special chars, unicode)
    - Verify output contains service name and valid ISO 8601 timestamp
    - Use `@settings(max_examples=100)` minimum
    - **Validates: Requirements 8.2**

  - [~] 1.13 Write property tests for task failure logging (Property 5)
    - **Property 5: Task failure logging includes all required fields with stderr truncation**
    - Test with random task names × exit codes (1–255) × random stderr strings (0–5000 chars)
    - Verify log contains ISO 8601 timestamp, task name, exit code, and at most first 1000 chars of stderr
    - Use `@settings(max_examples=100)` minimum
    - **Validates: Requirements 6.5**

  - [~] 1.14 Write property tests for overlapping task prevention (Property 6)
    - **Property 6: Overlapping task execution is prevented**
    - Test with random task names × random elapsed times
    - Verify skip behavior and warning log contains task name and elapsed time
    - Use `@settings(max_examples=100)` minimum
    - **Validates: Requirements 6.7**

  - [~] 1.15 Write property tests for invalid log level fallback (Property 7)
    - **Property 7: Invalid log level falls back to INFO with warning**
    - Test with random strings not in {DEBUG, INFO, WARNING, ERROR}
    - Verify effective level is INFO and warning log indicates invalid value
    - Use `@settings(max_examples=100)` minimum
    - **Validates: Requirements 8.4**

- [~] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Implement TJ Core Service
  - [~] 3.1 Create TJ Core Dockerfile and entrypoint
    - Create `services/tj-core/Dockerfile` based on `ruby:3.2-slim`
    - Install TaskJuggler gem (`tj3`) with all dependencies
    - Create `services/tj-core/entrypoint.sh` that validates `TJ_PROJECT_FILE` env var, verifies project file exists, and keeps container alive awaiting exec triggers
    - Configure health check: `tj3 --version`
    - _Requirements: 3.1, 3.2, 2.5, 2.6_

  - [~] 3.2 Create compilation script
    - Create `services/tj-core/scripts/compile.sh`
    - Run `tj3 /app/project/${TJ_PROJECT_FILE}` with output directed to `/app/reports`
    - On success: log timestamp + report count using the shared log format, exit 0
    - On failure: log full tj3 error output to stderr, exit non-zero
    - Clear previous reports before writing new ones
    - _Requirements: 3.3, 3.4, 3.5, 3.6, 8.1, 8.2_

  - [~] 3.3 Write unit tests for compilation script logic
    - Test success logging format (timestamp, report count)
    - Test failure logging (full error output preserved)
    - Test report directory cleanup before new compilation
    - _Requirements: 3.4, 3.5, 3.6_

- [ ] 4. Implement TJ Web Service
  - [~] 4.1 Create TJ Web Dockerfile and entrypoint
    - Create `services/tj-web/Dockerfile` based on `ruby:3.2-slim`
    - Install TaskJuggler gem (`tj3d`, `tj3webd`) and curl for health checks
    - Create `services/tj-web/entrypoint.sh` with process supervision (bash trap-based wrapper) that starts `tj3d` and `tj3webd`, restarts either if it exits within 30 seconds
    - Configure health check: `curl -f http://localhost:8080/`
    - _Requirements: 4.1, 4.2, 4.5, 4.6_

  - [~] 4.2 Create fallback status page
    - Create `services/tj-web/static/no-reports.html` — static HTML page indicating reports have not yet been generated
    - Configure entrypoint to serve this page when no reports exist in the report volume
    - _Requirements: 4.7_

  - [~] 4.3 Write unit tests for web service entrypoint logic
    - Test process restart behavior
    - Test fallback page serving condition
    - _Requirements: 4.5, 4.7_

- [ ] 5. Implement Mail Service
  - [~] 5.1 Create Mail Service Dockerfile and configuration
    - Create `services/tj-mail/Dockerfile` based on `alpine:3.19`
    - Install Postfix and procmail/maildrop for local delivery
    - Create `services/tj-mail/entrypoint.sh` that configures Postfix with mail domain from env, sets up SMTP relay with credentials from env
    - Configure health check: `postfix status`
    - _Requirements: 5.1, 5.2, 5.5, 5.6_

  - [~] 5.2 Create inbound email processing pipeline
    - Create `services/tj-mail/scripts/process-email.sh` — local delivery script (procmail recipe or Postfix pipe transport)
    - Extract attachments from incoming email
    - Validate: `.tji` extension, attachment ≤ 1 MB, total message ≤ 5 MB
    - Copy valid attachments to timesheet volume (`/app/timesheets`)
    - Reject invalid emails with logged reason (sender, subject, rejection cause)
    - _Requirements: 5.3, 5.7, 5.8, 5.9_

  - [~] 5.3 Create timesheet collection and reminder scripts
    - Create `services/tj-mail/scripts/collect-timesheets.sh` — processes any pending emails and ensures all valid timesheets are stored in the project volume
    - Create `services/tj-mail/scripts/send-reminders.sh` — sends timesheet reminder emails using configured sender address
    - _Requirements: 5.4, 5.5, 6.3, 6.4_

  - [~] 5.4 Write unit tests for email processing pipeline
    - Test valid attachment acceptance (`.tji`, ≤ 1 MB)
    - Test rejection of non-`.tji` attachments
    - Test rejection of oversized attachments (> 1 MB)
    - Test rejection of oversized emails (> 5 MB)
    - Test rejection logging format
    - _Requirements: 5.7, 5.8, 5.9_

- [ ] 6. Implement Cron Service
  - [~] 6.1 Create Cron Service Dockerfile and entrypoint
    - Create `services/tj-cron/Dockerfile` based on `alpine:3.19`
    - Install Supercronic and Docker CLI
    - Create `services/tj-cron/entrypoint.sh` that generates `/app/crontab` from environment variables (`TJ_CRON_COMPILE`, `TJ_CRON_TIMESHEETS`, `TJ_CRON_REMINDERS`), validates Docker socket access, sets timezone, and starts Supercronic
    - Configure health check: `pgrep supercronic`
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.6_

  - [~] 6.2 Create task execution wrapper script
    - Create `services/tj-cron/scripts/run-task.sh`
    - Implement lock file mechanism (prevents overlapping executions)
    - Create lock file with PID and start timestamp
    - Execute task with configurable timeout (default: 300s from `TJ_TASK_TIMEOUT`)
    - On success: log completion with timestamp and task name
    - On failure: log timestamp, task name, exit code, first 1000 chars of stderr
    - On timeout: kill process, log timeout warning
    - On overlap: skip execution, log warning with task name and elapsed time
    - Remove lock file on exit (trap-based cleanup)
    - _Requirements: 6.5, 6.7, 6.8_

  - [~] 6.3 Write unit tests for task execution wrapper
    - Test lock file creation and cleanup
    - Test overlap detection and skip behavior
    - Test timeout handling
    - Test stderr truncation to 1000 characters
    - Test success and failure logging format
    - _Requirements: 6.5, 6.7, 6.8_

- [~] 7. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Create Docker Compose file and wire services together
  - [~] 8.1 Create docker-compose.yml
    - Define all four services (`tj-core`, `tj-web`, `tj-mail`, `tj-cron`) in a single `docker-compose.yml`
    - Configure `depends_on` with `condition: service_healthy`: `tj-web` depends on `tj-core`, `tj-cron` depends on `tj-mail`
    - Define named volumes: `project-data`, `report-data`, `timesheet-data`, `mail-spool`
    - Define internal bridge network `tj-net` for inter-service communication
    - Configure `restart: unless-stopped` for all services
    - Configure `env_file: .env` for all services
    - Map `TJ_WEB_PORT` to host, keep all other ports internal
    - Configure health checks for all services (interval: 30s, timeout: 10s, retries: 3)
    - Use bind mount for `TJ_PROJECT_PATH` to `project-data` volume
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 7.5_

  - [~] 8.2 Create startup validation and initialization
    - Create shared validation entrypoint logic that checks required env vars before service start
    - Ensure first-time startup initializes all volumes and configurations automatically
    - Ensure subsequent starts reuse existing volumes without re-initialization
    - _Requirements: 2.3, 2.5, 2.6, 7.4_

- [ ] 9. Implement manual trigger scripts
  - [~] 9.1 Create scripts/rebuild.sh
    - Create `scripts/rebuild.sh` — host-executable bash script that triggers project compilation
    - Check Docker CLI is available, check `tj-core` container is running
    - Check lock file inside container (same mechanism as cron task wrapper) to prevent duplicate execution
    - Execute `docker exec tj-core /app/scripts/compile.sh`
    - Produce colored terminal output: blue `→` for starting, green `✓` for success, red `✗` for failure
    - On lock file conflict: print yellow `⚠` warning with lock timestamp and stale-lock removal hint
    - On container not running: print error with `docker compose up -d` guidance
    - Make script executable (`chmod +x`)
    - _Requirements: 10.1, 10.4, 10.5, 10.6_

  - [~] 9.2 Create scripts/collect-timesheets.sh
    - Create `scripts/collect-timesheets.sh` — host-executable bash script that triggers timesheet collection
    - Check Docker CLI is available, check `tj-mail` container is running
    - Check lock file inside container to prevent duplicate execution
    - Execute `docker exec tj-mail /app/scripts/collect-timesheets.sh`
    - Produce colored terminal output with same status indicators as rebuild.sh
    - Handle all error conditions (container not running, lock file exists, operation failure)
    - Make script executable (`chmod +x`)
    - _Requirements: 10.2, 10.4, 10.5, 10.6_

  - [~] 9.3 Create scripts/send-reminders.sh
    - Create `scripts/send-reminders.sh` — host-executable bash script that triggers reminder emails
    - Check Docker CLI is available, check `tj-mail` container is running
    - Check lock file inside container to prevent duplicate execution
    - Execute `docker exec tj-mail /app/scripts/send-reminders.sh`
    - Produce colored terminal output with same status indicators as rebuild.sh
    - Handle all error conditions (container not running, lock file exists, operation failure)
    - Make script executable (`chmod +x`)
    - _Requirements: 10.3, 10.4, 10.5, 10.6_

  - [~] 9.4 Write integration tests for manual trigger scripts
    - Test rebuild.sh succeeds when tj-core container is running and no lock file exists
    - Test collect-timesheets.sh succeeds when tj-mail container is running and no lock file exists
    - Test send-reminders.sh succeeds when tj-mail container is running and no lock file exists
    - Test all scripts refuse to run when target container is not running (exit code 1, helpful message)
    - Test all scripts refuse to run when lock file exists (exit code 1, warning with timestamp)
    - Test scripts work independently of tj-cron container (cron service stopped)
    - _Requirements: 10.1, 10.2, 10.3, 10.5, 10.6_

- [~] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Write user guide and rewrite README
  - [~] 11.1 Create docs/user-guide.md
    - Create `docs/user-guide.md` with the following sections:
      - Section 1: Introduction — what the system provides, prerequisites (Docker, Docker Compose)
      - Section 2: Day-to-Day Usage — viewing reports in the browser, understanding report types (Gantt, resource, task list, cost), checking system status (`docker compose ps`, logs)
      - Section 3: Timesheet Submission — email-based submission (format, addressing, attachment requirements, confirmation), web-based submission (accessing UI, upload workflow), timesheet file format reference
      - Section 4: Manual Operations — triggering a project rebuild (`scripts/rebuild.sh`), collecting timesheets on demand (`scripts/collect-timesheets.sh`), sending reminders manually (`scripts/send-reminders.sh`), usage examples with expected output, handling "already running" scenarios
      - Section 5: Customizing Your Project — replacing the sample project, modifying resources/tasks/reports, adding new report types, changing schedules and timezone, configuring email settings
      - Section 6: Configuration Reference — complete `.env` variable reference, cron schedule syntax, volume mount options
      - Section 7: Troubleshooting — service startup failures, compilation errors, email delivery problems, permission issues, reports not updating, checking logs
      - Section 8: Architecture Overview — service diagram (simplified), how services communicate, volume and data flow
    - Write in task-oriented style ("How do I...") for users comfortable with Docker but new to TaskJuggler
    - Include copy-pasteable command examples for every operation
    - Cross-reference TaskJuggler documentation for TJP syntax details
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 10.7_

  - [~] 11.2 Rewrite README.md
    - Rewrite repository root `README.md` as a concise getting-started document:
      - One-paragraph description of what the system provides
      - Quick Start section (clone, cp .env.example .env, docker compose up, open browser)
      - What's Included — brief bullet list of services and capabilities (4–5 items)
      - Documentation section with links to user guide, configuration reference, and sample project README
      - Project Structure — brief tree showing key directories (services/, scripts/, docs/, project/)
      - License line
    - Ensure README fits on one screen, is action-oriented, and does not duplicate user guide content
    - Link to `docs/user-guide.md` for detailed information, `project/README.md` for sample project details
    - _Requirements: 11.7, 11.8_

- [ ] 12. Integration testing and final validation
  - [~] 12.1 Write integration tests for stack startup and volume sharing
    - Test all services reach healthy state within 60 seconds
    - Test volume sharing: write file in one container, read from another
    - Test compilation pipeline: place `.tjp` file → trigger compile → verify reports appear
    - Test web serving: compile reports → HTTP GET → verify 200 response
    - _Requirements: 1.6, 3.5, 4.3, 7.2_

  - [~] 12.2 Write integration tests for email and cron workflows
    - Test email reception: send SMTP email with `.tji` attachment → verify file in timesheets volume
    - Test cron execution: wait for scheduled task → verify execution log
    - Test invalid email rejection and logging
    - _Requirements: 5.3, 5.7, 6.2, 6.5_

  - [~] 12.3 Write integration tests for sample project compilation
    - Test that the comprehensive sample project compiles with zero errors via `tj3`
    - Test that all four report types (Gantt, resource usage, task list, cost) are generated successfully
    - Test that timesheet files are syntactically valid and can be processed by the scheduler
    - Test that the modular include structure resolves correctly (no missing file errors)
    - _Requirements: 9.9, 9.4, 9.5, 9.6_

  - [~] 12.4 Write end-to-end test for full workflow
    - Test `docker compose up` with default config → all health checks pass within 120 seconds
    - Test sample project compiles → reports visible via web interface HTTP 200
    - Test full timesheet workflow: email → processed → included in next compilation
    - Test manual trigger scripts execute successfully against running stack
    - _Requirements: 7.2, 7.6, 9.9, 10.1, 10.2, 10.3_

- [~] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Python utilities use uv for dependency management and pytest + hypothesis for testing
- Shell scripts use the shared log format: `[SERVICE_NAME] [ISO8601_TIMESTAMP] [LEVEL] message`
- All services log to stdout/stderr for Docker log collection
- The comprehensive sample project (tasks 1.3–1.8) is created early because it provides the foundational content needed for service testing and the out-of-the-box experience
- Sample project uses modular `.tji` include files to demonstrate best practices for TaskJuggler project organization
- Manual trigger scripts (task 9) are placed after the Cron Service because they use the same lock file mechanism and `docker exec` pattern
- Documentation (task 11) is placed after Docker Compose wiring because the user guide references all services, scripts, and configuration
- Tasks marked with `*` are optional and can be skipped for faster MVP
