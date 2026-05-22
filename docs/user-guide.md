# User Guide

## 1. Introduction

This system provides a complete TaskJuggler environment packaged as a Docker Compose stack. It includes:

- **Project scheduling and report generation** — the TaskJuggler core engine compiles your `.tjp` project files and produces HTML/CSV reports automatically on a schedule.
- **Browser-based report viewing** — a web interface serves generated reports (Gantt charts, resource usage, task lists, cost breakdowns) without requiring any local TaskJuggler installation.
- **Timesheet collection** — team members submit timesheets via email or the web UI; the system processes and incorporates them into the next compilation cycle.
- **Automated orchestration** — cron-based scheduling handles compilation, timesheet collection, and reminder emails without manual intervention.
- **Manual trigger scripts** — on-demand scripts let you kick off any operation immediately without waiting for the next scheduled run.

### Prerequisites

| Requirement | Minimum Version | Check Command |
|-------------|----------------|---------------|
| Docker | 20.10+ | `docker --version` |
| Docker Compose | 2.0+ (V2 plugin) | `docker compose version` |
| Bash | 4.0+ (for manual scripts) | `bash --version` |

The system runs on Linux, macOS, and Windows (via WSL2 or Docker Desktop).

---

## 2. Day-to-Day Usage

### How do I view project reports?

Open your browser and navigate to the web interface:

```
http://localhost:8080
```

If you changed the port in your `.env` file, use that port instead:

```
http://localhost:<TJ_WEB_PORT>
```

Reports are regenerated automatically every 15 minutes (default schedule). After the first compilation completes, you will see the latest reports. If no reports have been generated yet, a status page will indicate that compilation has not run.

### Understanding report types

The system generates four types of reports from the sample project:

| Report | What it shows |
|--------|---------------|
| **Gantt Chart** | Visual timeline of all tasks with dependencies, milestones, and critical path highlighted. Use this to see the overall project schedule at a glance. |
| **Resource Usage** | How each team member is allocated over time, showing utilization percentages and scheduling conflicts. |
| **Task List** | A flat table of all tasks with start/end dates, effort, cost, and completion status. Useful for status meetings. |
| **Cost Report** | Financial breakdown by cost account showing planned vs. actual costs per phase and team. |

### How do I check system status?

See which services are running:

```bash
docker compose ps
```

Expected output when healthy:

```
NAME       SERVICE    STATUS                  PORTS
tj-core    tj-core    running (healthy)
tj-web     tj-web     running (healthy)       0.0.0.0:8080->8080/tcp
tj-mail    tj-mail    running (healthy)
tj-cron    tj-cron    running (healthy)
```

View recent logs from all services:

```bash
docker compose logs --tail=50
```

View logs from a specific service:

```bash
docker compose logs tj-core --tail=20
docker compose logs tj-cron --tail=20
```

Follow logs in real time:

```bash
docker compose logs -f
```

---

## 3. Timesheet Submission

Team members report time spent on tasks by submitting timesheet files. There are two submission methods: email and web UI.

### Email-based submission

#### How do I submit a timesheet by email?

1. Create a timesheet file (see format below).
2. Attach it to an email.
3. Send the email to any address at the configured mail domain (e.g., `timesheets@taskjuggler.local`).

#### Email requirements

| Requirement | Details |
|-------------|---------|
| **Recipient** | Any address `@<TJ_MAIL_DOMAIN>` (configured in `.env`) |
| **Attachment** | A single `.tji` file |
| **Attachment size** | Must not exceed 1 MB |
| **Total email size** | Must not exceed 5 MB |
| **File extension** | Must be `.tji` |

#### What happens after I send it?

- **Valid submission**: The attachment is extracted and stored in the project's `timesheets/` directory. It will be incorporated into the next project compilation.
- **Invalid submission**: The email is rejected and the system logs the sender address, subject line, and reason for rejection (wrong extension, oversized attachment, oversized email).

#### Common rejection reasons

| Reason | Fix |
|--------|-----|
| Attachment does not have `.tji` extension | Rename your file to end in `.tji` |
| Attachment exceeds 1 MB | Reduce file content or split into multiple periods |
| Total email exceeds 5 MB | Remove unnecessary email content or large signatures |

### Web-based submission

#### How do I submit a timesheet through the web UI?

1. Open the web interface at `http://localhost:8080`.
2. Navigate to the timesheet submission section.
3. Upload your `.tji` file using the upload form.
4. The file is stored directly in the project volume for processing.

The web submission bypasses email entirely — the file goes straight into the `timesheets/` directory.

### Timesheet file format reference

Timesheets use TaskJuggler's timesheet syntax. Here is a complete example:

```tjp
timesheet alice 2024-01-15 +1w {
  task acme_web.dev.backend.schema {
    work 32h
    status green "Schema design completed" {
      summary "Finalized database schema for all entities"
    }
  }
  task acme_web.dev.backend.endpoints {
    work 8h
    status yellow "Started endpoint scaffolding"
  }
}
```

#### Format breakdown

| Element | Description |
|---------|-------------|
| `timesheet <resource_id> <start_date> <duration>` | Header: who, when, how long |
| `task <task_path>` | Fully qualified task identifier from the project |
| `work <hours>` | Time spent on this task during the period |
| `status <color> "<headline>"` | Progress indicator: `green`, `yellow`, or `red` |
| `summary "<text>"` | Optional detailed description of work done |

#### Naming convention

Use the pattern: `YYYY-Www-<resource_id>.tji`

Examples:
- `2024-W03-alice.tji`
- `2024-W04-bob.tji`

For full timesheet syntax details, see the [TaskJuggler Timesheet documentation](https://taskjuggler.org/tj3/manual/timesheet.html).

---

## 4. Manual Operations

Three scripts in the `scripts/` directory let you trigger operations on demand without waiting for the cron schedule.

### How do I trigger a project rebuild?

```bash
./scripts/rebuild.sh
```

Expected output on success:

```
→ Triggering project compilation...
✓ Compilation completed successfully.
```

This runs the same compilation that the cron service executes every 15 minutes. Use it after modifying project files to see updated reports immediately.

### How do I collect timesheets on demand?

```bash
./scripts/collect-timesheets.sh
```

Expected output on success:

```
→ Triggering timesheet collection...
✓ Timesheet collection completed successfully.
```

This processes any pending timesheet emails that have arrived since the last collection.

### How do I send reminder emails manually?

```bash
./scripts/send-reminders.sh
```

Expected output on success:

```
→ Triggering reminder emails...
✓ Reminder emails sent successfully.
```

This sends the same reminder emails that normally go out weekly on Monday at 09:00.

### Error scenarios

#### Container not running

```
✗ Container 'tj-core' is not running.
  Start the stack with: docker compose up -d
```

**Fix**: Start the stack first with `docker compose up -d`.

#### Operation already in progress

```
⚠ Operation already in progress (lock file exists).
  Lock info: 2024-01-15T10:30:00Z PID=42
  If this is stale, remove it with: docker exec tj-core rm /tmp/tj-compile.lock
```

This means the same operation is already running (triggered by cron or another manual invocation). The system prevents duplicate executions.

**If the lock is stale** (the previous run crashed without cleanup):

```bash
docker exec tj-core rm /tmp/tj-compile.lock
```

Then retry the script.

#### Docker not available

```
✗ Docker CLI is not available.
  Please install Docker: https://docs.docker.com/get-docker/
```

**Fix**: Install Docker or ensure it is in your `PATH`.

### Script independence

The manual scripts work independently of the cron service. They only require:
1. Docker CLI available on the host
2. The target service container running (`tj-core` or `tj-mail`)

You can stop the cron service entirely and rely solely on manual triggers if preferred:

```bash
docker compose stop tj-cron
```

---

## 5. Customizing Your Project

### How do I replace the sample project with my own?

1. Stop the stack:

   ```bash
   docker compose down
   ```

2. Replace the contents of the `project/` directory with your own TaskJuggler files. Keep the same structure:

   ```
   project/
   ├── your-project.tjp        # Main project file
   ├── includes/               # Modular include files
   │   ├── resources.tji
   │   ├── tasks.tji
   │   └── reports.tji
   └── timesheets/             # Timesheet submissions land here
   ```

3. Update `.env` to point to your main project file:

   ```ini
   TJ_PROJECT_FILE=your-project.tjp
   ```

4. Start the stack:

   ```bash
   docker compose up -d
   ```

5. Trigger an immediate compilation to verify:

   ```bash
   ./scripts/rebuild.sh
   ```

### How do I modify resources, tasks, and reports?

Edit the include files in `project/includes/`:

| File | Contains |
|------|----------|
| `resources.tji` | Team members, working hours, vacation, rates |
| `tasks.tji` | Task hierarchy, dependencies, milestones, allocations |
| `reports.tji` | Report definitions (what reports to generate) |
| `accounts.tji` | Cost account structure for financial tracking |

After editing, trigger a rebuild to see your changes:

```bash
./scripts/rebuild.sh
```

### How do I add a new report type?

Add a report definition to `project/includes/reports.tji`. Example — a milestone report:

```tjp
taskreport "Milestones" {
  formats html
  columns name, start, end, status
  hideresource 1
  hidetask ~ismilestone(plan)
  sortmode plan.start.up
}
```

Then rebuild:

```bash
./scripts/rebuild.sh
```

The new report appears in the web interface after compilation completes.

For the full report syntax reference, see the [TaskJuggler Report documentation](https://taskjuggler.org/tj3/manual/report.html).

### How do I change schedules and timezone?

Edit your `.env` file:

```ini
# Run compilation every 5 minutes instead of 15
TJ_CRON_COMPILE=*/5 * * * *

# Collect timesheets every 30 minutes
TJ_CRON_TIMESHEETS=*/30 * * * *

# Send reminders on Friday at 16:00
TJ_CRON_REMINDERS=0 16 * * 5

# Use Stockholm timezone
TJ_TIMEZONE=Europe/Stockholm
```

Restart the cron service to apply schedule changes:

```bash
docker compose restart tj-cron
```

### How do I configure email settings?

Edit your `.env` file with your SMTP relay details:

```ini
TJ_MAIL_DOMAIN=yourcompany.com
TJ_SMTP_HOST=smtp.yourcompany.com
TJ_SMTP_PORT=587
TJ_SMTP_USER=taskjuggler@yourcompany.com
TJ_SMTP_PASSWORD=your-app-password
TJ_MAIL_SENDER=taskjuggler@yourcompany.com
```

Restart the mail service:

```bash
docker compose restart tj-mail
```

---

## 6. Configuration Reference

### Complete `.env` variable reference

Copy `.env.example` to `.env` and adjust values:

```bash
cp .env.example .env
```

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TJ_PROJECT_PATH` | No | `./project` | Host path to TaskJuggler project files (bind mount source) |
| `TJ_PROJECT_FILE` | No | `project.tjp` | Main project file name (must end in `.tjp`) |
| `TJ_WEB_PORT` | No | `8080` | Host port for the web interface (1–65535) |
| `TJ_MAIL_DOMAIN` | **Yes** | — | Mail domain for receiving timesheet submissions |
| `TJ_SMTP_HOST` | **Yes** | — | Outbound SMTP relay host |
| `TJ_SMTP_PORT` | **Yes** | — | Outbound SMTP relay port (25, 465, or 587) |
| `TJ_SMTP_USER` | No | _(empty)_ | SMTP authentication username |
| `TJ_SMTP_PASSWORD` | No | _(empty)_ | SMTP authentication password |
| `TJ_MAIL_SENDER` | No | `taskjuggler@<TJ_MAIL_DOMAIN>` | Sender address for outgoing emails |
| `TJ_CRON_COMPILE` | No | `*/15 * * * *` | Project compilation schedule |
| `TJ_CRON_TIMESHEETS` | No | `0 * * * *` | Timesheet collection schedule |
| `TJ_CRON_REMINDERS` | No | `0 9 * * 1` | Reminder email schedule |
| `TJ_TIMEZONE` | No | `UTC` | IANA timezone for all services and cron |
| `TJ_LOG_LEVEL` | No | `INFO` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `TJ_TASK_TIMEOUT` | No | `300` | Cron task timeout in seconds (must be > 0) |

If a required variable is missing or empty, the system refuses to start and prints an error identifying the missing variable.

### Cron schedule syntax

Schedules use standard 5-field cron expressions:

```
┌───────────── minute (0–59)
│ ┌───────────── hour (0–23)
│ │ ┌───────────── day of month (1–31)
│ │ │ ┌───────────── month (1–12)
│ │ │ │ ┌───────────── day of week (0–7, 0 and 7 = Sunday)
│ │ │ │ │
* * * * *
```

Common examples:

| Expression | Meaning |
|------------|---------|
| `*/15 * * * *` | Every 15 minutes |
| `0 * * * *` | Every hour at minute 0 |
| `0 9 * * 1` | Every Monday at 09:00 |
| `0 */6 * * *` | Every 6 hours |
| `30 8 * * 1-5` | Weekdays at 08:30 |
| `0 0 1 * *` | First day of each month at midnight |

Use [crontab.guru](https://crontab.guru/) to build and validate expressions.

### Volume mount options

The system uses Docker volumes for persistent data:

| Volume | Purpose | Mounted in |
|--------|---------|------------|
| `report-data` | Generated HTML/CSV reports | `tj-core` (RW), `tj-web` (RO) |
| `timesheet-data` | Submitted timesheet `.tji` files | `tj-mail` (RW), `tj-core` (RO) |
| `mail-spool` | Postfix mail queue | `tj-mail` (RW) |

The project directory is a bind mount from the host:

```yaml
${TJ_PROJECT_PATH:-./project}:/app/project
```

To use a different project directory on the host:

```ini
TJ_PROJECT_PATH=/path/to/your/project
```

---

## 7. Troubleshooting

### Service startup failures

**Symptom**: `docker compose up` fails or a service stays in "restarting" state.

Check which services are unhealthy:

```bash
docker compose ps
```

View startup logs for the failing service:

```bash
docker compose logs tj-core --tail=30
docker compose logs tj-mail --tail=30
```

**Common causes**:

| Cause | Error message | Fix |
|-------|---------------|-----|
| Missing required env var | `ERROR: TJ_SMTP_HOST is required but not set` | Add the variable to your `.env` file |
| Port already in use | `bind: address already in use` | Change `TJ_WEB_PORT` in `.env` or stop the conflicting process |
| Invalid log level | `WARNING: Invalid TJ_LOG_LEVEL 'VERBOSE', falling back to INFO` | Use one of: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

### Compilation errors

**Symptom**: Reports are not updating; `rebuild.sh` exits with a non-zero code.

Check compilation output:

```bash
docker compose logs tj-core --tail=50
```

Or trigger a manual rebuild and observe the output:

```bash
./scripts/rebuild.sh
```

**Common causes**:

| Cause | Fix |
|-------|-----|
| Syntax error in `.tjp`/`.tji` file | Check the error output for line numbers; fix the syntax. See [TJP syntax reference](https://taskjuggler.org/tj3/manual/). |
| Missing include file | Ensure all files referenced by `include` directives exist in the project directory |
| Undefined resource or task ID | Verify resource/task IDs match between timesheets and project definitions |
| Circular dependency | Review task `depends` and `precedes` declarations for loops |

### Email delivery problems

**Symptom**: Timesheets sent by email are not appearing in the project.

Check mail service logs:

```bash
docker compose logs tj-mail --tail=30
```

**Common causes**:

| Cause | Fix |
|-------|-----|
| SMTP relay rejecting connection | Verify `TJ_SMTP_HOST`, `TJ_SMTP_PORT`, `TJ_SMTP_USER`, `TJ_SMTP_PASSWORD` in `.env` |
| Attachment rejected (wrong extension) | Ensure the file ends in `.tji` |
| Attachment rejected (too large) | Keep attachments under 1 MB |
| Email rejected (total size > 5 MB) | Reduce email size |
| Mail domain misconfigured | Verify `TJ_MAIL_DOMAIN` matches where you are sending emails |

### Permission issues

**Symptom**: Services fail with "permission denied" errors.

```bash
docker compose logs --tail=20 | grep -i permission
```

**Common causes**:

| Cause | Fix |
|-------|-----|
| Docker socket not accessible | Ensure your user is in the `docker` group: `sudo usermod -aG docker $USER` |
| Project directory not readable | Check host directory permissions: `ls -la ./project/` |
| Volume mount ownership mismatch | The containers run as root by default; ensure host files are world-readable or owned by UID 0 |

### Reports not updating

**Symptom**: The web interface shows stale reports.

1. Check if the cron service is running:

   ```bash
   docker compose ps tj-cron
   ```

2. Check cron logs for errors:

   ```bash
   docker compose logs tj-cron --tail=20
   ```

3. Check for a stale lock file:

   ```bash
   docker exec tj-core test -f /tmp/tj-compile.lock && echo "LOCKED" || echo "OK"
   ```

   If locked, check how long it has been:

   ```bash
   docker exec tj-core cat /tmp/tj-compile.lock
   ```

   Remove a stale lock:

   ```bash
   docker exec tj-core rm /tmp/tj-compile.lock
   ```

4. Trigger a manual rebuild:

   ```bash
   ./scripts/rebuild.sh
   ```

### Checking logs

All services log to stdout/stderr in a structured format:

```
[SERVICE_NAME] [ISO8601_TIMESTAMP] [LEVEL] message
```

Useful log commands:

```bash
# All services, last 100 lines
docker compose logs --tail=100

# Single service, follow in real time
docker compose logs -f tj-core

# Filter for errors only
docker compose logs | grep '\[ERROR\]'

# Filter for a specific time range (requires grep)
docker compose logs | grep '2024-01-15T10:3'
```

---

## 8. Architecture Overview

### Service diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                       │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐│
│  │ tj-core  │   │  tj-web  │   │ tj-mail  │   │ tj-cron  ││
│  │          │   │          │   │          │   │          ││
│  │ tj3      │   │ tj3d     │   │ Postfix  │   │Supercronic││
│  │ compiler │   │ tj3webd  │   │ MTA      │   │          ││
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘│
│       │               │               │               │      │
│       └───────────────┴───────────────┴───────────────┘      │
│                    Internal Network (tj-net)                  │
└─────────────────────────────────────────────────────────────┘
         │               │               │
         ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ project-data │ │ report-data  │ │  mail-spool  │
│ .tjp/.tji    │ │ HTML/CSV     │ │ Postfix queue│
└──────────────┘ └──────────────┘ └──────────────┘
```

### How services communicate

| From | To | Mechanism | Purpose |
|------|----|-----------|---------|
| `tj-cron` | `tj-core` | `docker exec` via Docker socket | Trigger project compilation |
| `tj-cron` | `tj-mail` | `docker exec` via Docker socket | Trigger timesheet collection and reminders |
| `tj-core` | `tj-web` | Shared `report-data` volume | Reports written by core, served by web |
| `tj-mail` | `tj-core` | Shared `timesheet-data` volume | Timesheets stored by mail, read during compilation |
| User browser | `tj-web` | HTTP on port 8080 (configurable) | View reports, submit timesheets |
| User email | `tj-mail` | SMTP on port 25 (internal network) | Submit timesheets via email |
| `tj-mail` | External SMTP | SMTP relay (configured in `.env`) | Send reminder and notification emails |

### Volume and data flow

```
User edits .tjp/.tji files
        │
        ▼
┌─────────────────┐         ┌─────────────────┐
│  project-data   │────────▶│    tj-core      │
│  (bind mount)   │         │  compiles .tjp  │
└─────────────────┘         └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │  report-data    │
                            │  (HTML/CSV)     │
                            └────────┬────────┘
                                     │
                                     ▼
                            ┌─────────────────┐
                            │    tj-web       │
                            │  serves reports │
                            └─────────────────┘
                                     │
                                     ▼
                               User Browser


Email with .tji attachment
        │
        ▼
┌─────────────────┐         ┌─────────────────┐
│    tj-mail      │────────▶│ timesheet-data  │
│  validates &    │         │  (.tji files)   │
│  extracts       │         └────────┬────────┘
└─────────────────┘                  │
                                     ▼
                            ┌─────────────────┐
                            │    tj-core      │
                            │  includes in    │
                            │  next compile   │
                            └─────────────────┘
```

### Orchestration cycle

The cron service drives the automated workflow:

1. **Every 15 minutes** (default): Triggers `tj-core` to compile the project → fresh reports appear in the web UI.
2. **Every hour** (default): Triggers `tj-mail` to process received emails → new timesheets are stored for the next compilation.
3. **Weekly Monday 09:00** (default): Triggers `tj-mail` to send reminder emails → team members are prompted to submit timesheets.

All schedules are configurable via `.env`. The cron service prevents overlapping executions using lock files — if a task is still running when its next execution is due, the new execution is skipped and a warning is logged.
