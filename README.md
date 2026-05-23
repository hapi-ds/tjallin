# tjallin 

(from "TaskJuggler All-In") provides an out-of-the-box, fully containerized environment for TaskJuggler, the powerful text-based project management tool. By leveraging Docker Compose, this setup orchestrates everything you need into a single stack: the TaskJuggler core, an automated web server to host compiled HTML reports, and an integrated open-source mail client for managing project communications and automated alerts.

Clone, configure, and run — reports are visible in your browser within minutes.

## Quick Start

```bash
git clone <repository-url> && cd tjallin
cp .env.example .env        # edit .env to set SMTP credentials
docker compose up -d
open http://localhost:8080   # view generated reports
open http://localhost:9090   # admin panel (rebuild, status)
```

The included sample project compiles automatically on first startup. Edit `.env` to configure mail relay, schedules, and timezone.

## Manual Operations

Trigger operations on demand without waiting for the cron schedule:

```bash
docker compose exec tj-core /app/scripts/compile.sh          # Rebuild reports
docker compose exec tj-mail /app/scripts/collect-timesheets.sh  # Process pending timesheets
docker compose exec tj-mail /app/scripts/send-reminders.sh      # Send reminder emails
```

On Linux/macOS/WSL, convenience wrapper scripts are also available in `scripts/`.

## What's Included

- **TaskJuggler core** — compiles `.tjp` project files and generates HTML/CSV reports on a configurable schedule
- **Web interface** — serves Gantt charts, resource usage, task lists, and cost reports via HTTP
- **Mail service** — receives timesheet submissions by email and sends reminder notifications
- **Cron orchestration** — automates compilation, timesheet collection, and reminders
- **Manual trigger scripts** — trigger compilation, timesheet collection, or reminders on demand via `docker compose exec`
- **Admin panel** — browser-based interface at `http://localhost:9090` to trigger rebuilds and view system status

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/user-guide.md) | Day-to-day usage, timesheet submission, configuration reference, and troubleshooting |
| [Sample Project](project/README.md) | How the included demo project works and how to replace it with your own |
| [.env.example](.env.example) | All configurable parameters with defaults and descriptions |

## Project Structure

```
tjallin/
├── services/           # Dockerfiles and entrypoints for each service
│   ├── tj-core/       #   TaskJuggler compiler
│   ├── tj-web/        #   Web report server
│   ├── tj-mail/       #   Postfix mail service
│   └── tj-cron/       #   Supercronic scheduler
├── project/            # Sample TaskJuggler project (bind-mounted into containers)
├── scripts/            # Host-side manual trigger scripts
├── docs/               # User guide and documentation
├── docker-compose.yml  # Stack definition
└── .env.example        # Configuration template
```

## License

Licensed under the [Apache License 2.0](LICENSE).
