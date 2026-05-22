# Requirements Document

## Introduction

This feature provides an all-in-one Docker Compose system for TaskJuggler that integrates the core scheduling application, web services (taskjuggler-daemon and web interface), a mail server for timesheet exchange, and cron-based orchestration. The system is preconfigured to work out-of-the-box with minimal user configuration, enabling teams to deploy a complete TaskJuggler environment with a single `docker compose up` command. A comprehensive sample project is included that demonstrates TaskJuggler's full capabilities — including multi-resource scheduling, task dependencies, cost tracking, timesheet workflows, and multiple report types — serving as both a functional demo and an educational reference for new users.

## Glossary

- **Compose_System**: The Docker Compose orchestration layer that defines, configures, and runs all containers as a unified stack.
- **TJ_Core_Service**: The container running the TaskJuggler core application (`tj3` command-line tool) responsible for scheduling and report generation.
- **TJ_Web_Service**: The container running the TaskJuggler daemon (`tj3d`) and web server (`tj3webd`) that provides browser-based access to project reports.
- **Mail_Service**: The container running a mail transfer agent (MTA) configured to send and receive timesheet submissions via email.
- **Cron_Service**: The container or process responsible for executing scheduled tasks that coordinate report generation, timesheet collection, and mail delivery.
- **Environment_File**: A single `.env` file containing all user-configurable parameters for the stack (domain, credentials, paths, schedules).
- **Project_Volume**: A shared Docker volume or bind mount containing TaskJuggler project files (`.tjp`, `.tji`) accessible to services that need them.
- **Timesheet**: A TaskJuggler timesheet file (`.tji`) submitted by team members to report time spent on tasks.

## Requirements

### Requirement 1: Docker Compose Stack Definition

**User Story:** As a project manager, I want a single Docker Compose file that defines all TaskJuggler services, so that I can deploy the entire system with one command.

#### Acceptance Criteria

1. THE Compose_System SHALL define all services (TJ_Core_Service, TJ_Web_Service, Mail_Service, Cron_Service) in a single `docker-compose.yml` file.
2. WHEN `docker compose up` is executed, THE Compose_System SHALL start all services in dependency order where TJ_Core_Service starts before TJ_Web_Service, and Mail_Service starts before Cron_Service, using `depends_on` declarations.
3. THE Compose_System SHALL use named volumes for persistent data storage including project files, generated reports, and mail spool data, ensuring data survives container restarts.
4. WHEN a service container exits unexpectedly, THE Compose_System SHALL restart the container automatically using the `unless-stopped` restart policy.
5. THE Compose_System SHALL define an internal Docker network for inter-service communication and SHALL NOT expose inter-service ports to the host unless explicitly configured in the Environment_File.
6. WHEN `docker compose up` completes startup, THE Compose_System SHALL have all four services in a running state within 60 seconds.

### Requirement 2: Environment Configuration

**User Story:** As a system administrator, I want a single environment file with sensible defaults, so that I can configure the entire stack without editing multiple files.

#### Acceptance Criteria

1. THE Compose_System SHALL read all user-configurable parameters from a single Environment_File (`.env`).
2. THE Compose_System SHALL provide a `.env.example` file containing all configurable parameters with default values, where each parameter is accompanied by a comment describing its purpose and accepted values.
3. WHEN the Environment_File is not present, THE Compose_System SHALL use default values that start all services and make the web interface accessible on the default port.
4. THE Environment_File SHALL expose configuration for: project file host path (bind mount source), mail domain, SMTP credentials (host, port, username, password), cron schedules (standard 5-field cron expressions), web service port (1–65535, default: 8080), and timezone (IANA timezone identifier).
5. THE Compose_System SHALL validate that required environment variables (SMTP host, SMTP port, mail domain) are defined and non-empty before starting services.
6. IF a required environment variable is missing or empty, THEN THE Compose_System SHALL refuse to start and output an error message indicating which variable is missing.

### Requirement 3: TaskJuggler Core Service

**User Story:** As a project manager, I want the TaskJuggler core application available in a container, so that I can schedule projects and generate reports without local installation.

#### Acceptance Criteria

1. THE TJ_Core_Service SHALL include a working installation of TaskJuggler (`tj3`) with all dependencies such that `tj3 --version` executes successfully.
2. THE TJ_Core_Service SHALL mount the Project_Volume containing `.tjp` and `.tji` files as a readable and writable directory.
3. WHEN triggered by the Cron_Service, THE TJ_Core_Service SHALL compile the main project file configured in the Environment_File and write all generated reports to the shared report volume.
4. IF a project compilation fails (non-zero exit code from `tj3`), THEN THE TJ_Core_Service SHALL log the error to stdout/stderr including the full TaskJuggler error output and exit with a non-zero status code.
5. THE TJ_Core_Service SHALL make generated reports available to the TJ_Web_Service via a shared volume, replacing any previously generated reports from the prior compilation run.
6. WHEN project compilation completes successfully, THE TJ_Core_Service SHALL log a confirmation message to stdout including a timestamp and the number of reports generated.

### Requirement 4: TaskJuggler Web Service

**User Story:** As a team member, I want browser-based access to project reports and status pages, so that I can view schedules without command-line tools.

#### Acceptance Criteria

1. THE TJ_Web_Service SHALL run the TaskJuggler daemon (`tj3d`) and web server (`tj3webd`).
2. THE TJ_Web_Service SHALL expose the web interface on a configurable host port (default: 8080).
3. WHEN a user accesses the web interface, THE TJ_Web_Service SHALL serve the reports from the most recent successful project compilation available in the shared report volume.
4. WHEN a user submits a timesheet through the web interface, THE TJ_Web_Service SHALL store the submitted timesheet file in the Project_Volume for processing by the TJ_Core_Service.
5. WHILE the TJ_Web_Service is running, THE TJ_Web_Service SHALL keep the daemon process alive and restart it within 30 seconds if it exits unexpectedly.
6. IF the TJ_Web_Service daemon fails to start or becomes unresponsive to HTTP requests for more than 30 seconds, THEN THE TJ_Web_Service SHALL report an unhealthy status via its Docker health check.
7. IF no reports are available in the shared report volume, THEN THE TJ_Web_Service SHALL serve a status page indicating that no reports have been generated yet.

### Requirement 5: Mail Service for Timesheets

**User Story:** As a team member, I want to submit timesheets via email, so that I can report time without accessing the web interface directly.

#### Acceptance Criteria

1. THE Mail_Service SHALL run a mail transfer agent capable of sending and receiving email over SMTP on port 25 within the internal Docker network.
2. THE Mail_Service SHALL accept incoming email addressed to the mail domain configured in the Environment_File for timesheet submissions.
3. WHEN a timesheet email is received containing a valid timesheet attachment, THE Mail_Service SHALL store the attachment file in the Project_Volume timesheets directory within 30 seconds of receipt.
4. WHEN the Cron_Service triggers timesheet collection, THE Mail_Service SHALL have stored all previously received valid timesheet attachments in the Project_Volume such that no pending email remains unprocessed.
5. THE Mail_Service SHALL send outgoing notification emails (timesheet reminders, status reports) using the sender address configured in the Environment_File on behalf of the TJ_Core_Service.
6. THE Mail_Service SHALL support configurable SMTP relay for outbound mail delivery as specified in the Environment_File.
7. IF an incoming email does not contain a valid timesheet attachment, THEN THE Mail_Service SHALL reject the email and log the sender address, subject line, and reason for rejection.
8. THE Mail_Service SHALL consider an attachment valid only if it has a `.tji` file extension and does not exceed 1 MB in size.
9. IF an incoming email exceeds 5 MB total size, THEN THE Mail_Service SHALL reject the email and log the sender address and message size.

### Requirement 6: Cron-Based Orchestration

**User Story:** As a system administrator, I want scheduled tasks that coordinate all services, so that the system operates autonomously without manual intervention.

#### Acceptance Criteria

1. THE Cron_Service SHALL execute scheduled tasks defined in the Environment_File.
2. THE Cron_Service SHALL trigger project compilation on a configurable schedule (default: every 15 minutes).
3. THE Cron_Service SHALL trigger timesheet collection and processing on a configurable schedule (default: hourly).
4. THE Cron_Service SHALL trigger timesheet reminder emails on a configurable schedule (default: weekly on Monday at 09:00).
5. WHEN a scheduled task exits with a non-zero exit code or exceeds a configurable timeout (default: 300 seconds), THE Cron_Service SHALL log the failure with timestamp, task name, exit code, and the first 1000 characters of stderr output.
6. THE Cron_Service SHALL use the system timezone configured in the Environment_File.
7. IF a scheduled task is still running when its next scheduled execution is due, THEN THE Cron_Service SHALL skip the new execution and log a warning with the task name and elapsed time.
8. WHEN a scheduled task completes successfully, THE Cron_Service SHALL log the completion with timestamp and task name.

### Requirement 7: Out-of-the-Box Operation

**User Story:** As a new user, I want the system to work immediately after cloning the repository, so that I can evaluate TaskJuggler without complex setup.

#### Acceptance Criteria

1. THE Compose_System SHALL include a sample TaskJuggler project file that demonstrates task scheduling, resource allocation, and report generation, and that compiles without errors when processed by the TJ_Core_Service.
2. WHEN started with default configuration, THE Compose_System SHALL produce a deployment where all service health checks pass and the web interface returns an HTTP 200 response at `http://localhost:8080` within 120 seconds of the `docker compose up` command completing.
3. THE Compose_System SHALL include a README with setup instructions, architecture overview, and configuration reference.
4. WHEN started for the first time, THE Compose_System SHALL initialize all required volumes and configurations automatically without requiring manual intervention, and subsequent starts SHALL reuse existing volumes without re-initialization.
5. THE Compose_System SHALL include health checks for each service with an interval of 30 seconds, a timeout of 10 seconds, and 3 retries before marking a service as unhealthy.
6. WHEN started with default configuration, THE Compose_System SHALL generate viewable reports from the sample project file and serve them through the TJ_Web_Service web interface without additional user action.

### Requirement 8: Logging and Observability

**User Story:** As a system administrator, I want centralized logging from all services, so that I can diagnose issues without connecting to individual containers.

#### Acceptance Criteria

1. THE Compose_System SHALL configure all services to output logs to stdout/stderr for Docker log collection.
2. WHEN a service produces a log entry, THE Compose_System SHALL include the service name and an ISO 8601 timestamp in each log line.
3. THE Compose_System SHALL support configurable log levels (DEBUG, INFO, WARNING, ERROR) via the Environment_File, with a default level of INFO applied to all services when no level is specified.
4. IF the Environment_File specifies a log level value not in the set (DEBUG, INFO, WARNING, ERROR), THEN THE Compose_System SHALL fall back to the default level of INFO and log a warning indicating the invalid configuration.

### Requirement 9: Comprehensive Sample Project

**User Story:** As a new user, I want a detailed and realistic sample TaskJuggler project included in the repository, so that I can learn TaskJuggler's capabilities through a working example that demonstrates advanced features.

#### Acceptance Criteria

1. THE Compose_System SHALL include a sample project that defines multiple resources with different daily working hours, individual vacation periods, and distinct skill sets assigned via resource attributes.
2. THE Compose_System SHALL include a sample project that defines tasks with explicit dependencies (precedes, depends), named milestones, and a task structure that produces a visible critical path in generated reports.
3. THE Compose_System SHALL include a sample project that demonstrates resource allocation constraints (limits, mandatory/alternative allocations) and resource leveling by assigning resources to overlapping tasks that require the scheduler to resolve conflicts.
4. THE Compose_System SHALL include a sample project that generates multiple report types including a Gantt chart, a resource usage report, a task list report, and a cost report, each configured as a separate report definition.
5. THE Compose_System SHALL include sample timesheet files (`.tji`) representing submitted timesheets from at least two different resources for at least two reporting periods, demonstrating the timesheet workflow.
6. THE Compose_System SHALL organize the sample project using a modular structure with include files (`.tji`), separating at minimum resource definitions, task definitions, and report definitions into distinct files included by the main project file.
7. THE Compose_System SHALL include a sample project that defines resources with different cost rates (hourly or daily) and tasks with cost tracking enabled, such that the cost report produces meaningful financial data.
8. THE Compose_System SHALL include a sample project that organizes work into distinct project phases (planning, development, testing, deployment) with sub-projects or task groups within each phase, demonstrating hierarchical task decomposition.
9. WHEN the TJ_Core_Service compiles the sample project, THE Compose_System SHALL produce zero compilation errors and generate all defined reports successfully.
10. THE Compose_System SHALL include a README or documentation section within the sample project directory explaining the project structure, the purpose of each include file, and how users can modify the example to build their own projects.

### Requirement 10: Manual Trigger Scripts

**User Story:** As a system administrator, I want executable scripts that manually trigger the same operations as the cron jobs, so that I can kick off a project rebuild, timesheet collection, or reminder send at any time without waiting for the next scheduled run.

#### Acceptance Criteria

1. THE Compose_System SHALL provide a `scripts/rebuild.sh` script on the host that triggers the same project compilation operation as the Cron_Service scheduled compilation task.
2. THE Compose_System SHALL provide a `scripts/collect-timesheets.sh` script on the host that triggers the same timesheet collection operation as the Cron_Service scheduled timesheet collection task.
3. THE Compose_System SHALL provide a `scripts/send-reminders.sh` script on the host that triggers the same reminder email operation as the Cron_Service scheduled reminder task.
4. WHEN a manual trigger script is executed, THE Compose_System SHALL provide clear output to the user indicating the operation that is starting, its progress, and whether it completed successfully or failed.
5. THE Compose_System SHALL allow manual trigger scripts to execute at any time independently of the cron schedule without requiring the Cron_Service to be running.
6. WHEN a manual trigger script is executed while the same operation is already running (triggered by cron or another manual invocation), THE Compose_System SHALL respect the same lock file mechanism used by the Cron_Service and refuse to start a duplicate execution, informing the user that the operation is already in progress.
7. THE Compose_System SHALL document all manual trigger scripts in the user guide, including usage examples and expected output.

### Requirement 11: User Guide and README Rewrite

**User Story:** As a new or existing user, I want a comprehensive user guide for day-to-day operations and a concise README for getting started, so that I can quickly set up the system and find detailed usage instructions when needed.

#### Acceptance Criteria

1. THE Compose_System SHALL include a user guide document at `docs/user-guide.md` that covers day-to-day usage of the system including how to submit timesheets, how to view reports, how to trigger manual rebuilds, how to customize the project, and troubleshooting common issues.
2. THE Compose_System SHALL include a user guide that documents the manual trigger scripts with usage examples, expected output, and error scenarios.
3. THE Compose_System SHALL include a user guide that explains the timesheet submission workflow for both email-based and web-based submission methods.
4. THE Compose_System SHALL include a user guide that describes how to view and interpret generated reports through the web interface.
5. THE Compose_System SHALL include a user guide that provides troubleshooting guidance for common issues including service startup failures, compilation errors, email delivery problems, and permission issues.
6. THE Compose_System SHALL include a user guide that explains how to customize the sample project or replace it with a user's own TaskJuggler project.
7. THE Compose_System SHALL provide a README that serves as a concise getting-started document containing: a brief description of what the system is, a quick-start section (clone the repository and run `docker compose up`), and links to the user guide and configuration reference for detailed information.
8. THE Compose_System SHALL ensure the README does not duplicate detailed information found in the user guide, instead directing readers to the appropriate documentation section.
