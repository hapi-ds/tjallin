# tjallin 

from "TaskJuggler All-In", as a surname it is the diminutive form of the Old Frisian name Tjal, meaning to rule or to govern.

Tjallin provides an out-of-the-box, fully containerized environment for TaskJuggler, the powerful text-based project management tool. By leveraging Docker Compose, this setup orchestrates everything you need into a single stack: the TaskJuggler core, an automated web server to host compiled HTML reports with cross-linked navigation, and a self-contained mail service with SMTP and IMAP for managing project communications and automated alerts.

Clone, configure, and run — reports are visible in your browser within minutes. No external SMTP relay or mail credentials required.

## Quick Start

```bash
git clone <repository-url> && cd tjallin
cp .env.example .env        # edit .env to configure users and schedules
docker compose up -d
open http://localhost:8080   # view generated reports
open http://localhost:9090   # admin panel (rebuild, status)
```

The included sample project compiles automatically on first startup. Edit `.env` to configure mail users, schedules, and timezone. The stack is fully self-contained — no external SMTP relay is needed.

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
- **Cross-linked reports** — every report includes a navigation header with links to all other reports, a Report Index page, and the admin panel
- **Journal report** — displays project status entries and notes recorded against tasks, sorted newest-first
- **Web interface** — serves Gantt charts, resource usage, task lists, cost reports, and journal entries via HTTP
- **Self-contained mail service** — local SMTP delivery and IMAP access without external relay dependencies
- **IMAP access** — connect any standard mail client (Thunderbird, Apple Mail, etc.) to read timesheet reminders and notifications
- **Cron orchestration** — automates compilation, timesheet collection, and reminders
- **Manual trigger scripts** — trigger compilation, timesheet collection, or reminders on demand via `docker compose exec`
- **Admin panel** — browser-based interface at `http://localhost:9090` to trigger rebuilds and view system status

## Mail Service

The mail service is fully self-contained. It provides both SMTP (for sending/receiving within the stack) and IMAP (for reading mail with standard clients).

### Connecting a mail client

Connect your mail client to read notifications and reminders:

| Setting | Value |
|---------|-------|
| Protocol | IMAP |
| Host | `localhost` |
| Port | `1143` (configurable via `TJ_IMAP_PORT`) |
| Username | As configured in `TJ_MAIL_USERS` |
| Password | As configured in `TJ_MAIL_USERS` |
| Encryption | None (internal network) |

### Mail user configuration

Users are configured via the `TJ_MAIL_USERS` environment variable:

```bash
TJ_MAIL_USERS=alice:secret1,bob:secret2
```

If unset, a single default account is created from the `TJ_MAIL_SENDER` local-part.

### Optional external relay

For environments that need to forward mail externally, set:

```bash
TJ_SMTP_RELAY_HOST=smtp.example.com
TJ_SMTP_RELAY_PORT=25
```

When unset, all mail is delivered locally.

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
│   ├── tj-core/       #   TaskJuggler compiler + report post-processor
│   ├── tj-web/        #   Web report server
│   ├── tj-mail/       #   Postfix SMTP + Dovecot IMAP mail service
│   └── tj-cron/       #   Supercronic scheduler
├── src/tj_utils/       # Python utilities (mail user parsing, report post-processing)
├── project/            # Sample TaskJuggler project (bind-mounted into containers)
├── scripts/            # Host-side manual trigger scripts
├── tests/              # Unit, property-based, and integration tests
│   ├── unit/          #   Example-based unit tests
│   ├── property/      #   Hypothesis property-based tests
│   └── integration/   #   Docker-based integration tests
├── docs/               # User guide and documentation
├── docker-compose.yml  # Stack definition
└── .env.example        # Configuration template
```

## Development

The project uses `uv` for Python dependency management and `pytest` with `hypothesis` for testing.

```bash
uv sync                                          # install dependencies
uv run pytest tests/unit tests/property -q       # run unit + property tests
uv run pytest tests/integration -m integration   # run integration tests (requires Docker stack)
```

## License

Licensed under the [Apache License 2.0](LICENSE).
