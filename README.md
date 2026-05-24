# tjallin 

from "TaskJuggler All-In", as a surname it is the diminutive form of the Old Frisian name Tjal, meaning to rule or to govern.

Tjallin provides an out-of-the-box, fully containerized environment for TaskJuggler, the powerful text-based project management tool. By leveraging Docker Compose, this setup orchestrates everything you need into a single stack: the TaskJuggler core, an automated web server to host compiled HTML reports with cross-linked navigation, and a self-contained mail service with SMTP and IMAP for managing project communications and automated alerts.

Clone, configure, and run — reports are visible in your browser within minutes. No external SMTP relay or mail credentials required.

## Quick Start

```bash
git clone <repository-url> && cd tjallin
cp .env.example .env        # edit .env to configure users and schedules
docker compose up -d
open http://localhost:8080   # view generated reports and access admin/chat
```

The included sample project compiles automatically on first startup. Edit `.env` to configure mail users, schedules, and timezone. The stack is fully self-contained — no external SMTP relay is needed.

### Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **LM Studio** 0.2+ (for the agent chat feature) — download from [lmstudio.ai](https://lmstudio.ai). Load a model and start the local server (OpenAI-compatible API on `http://localhost:1234/v1` by default). The chat feature degrades gracefully if LM Studio is not running; reports and admin remain fully functional.

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
- **Unified web interface** — single NiceGUI app on port 8080 serving reports, admin panel, and agent chat
- **LLM agent chat** — conversational project management at `/chat` powered by a local LM Studio model (see below)
- **Self-contained mail service** — local SMTP delivery and IMAP access without external relay dependencies
- **IMAP access** — connect any standard mail client (Thunderbird, Apple Mail, etc.) to read timesheet reminders and notifications
- **Cron orchestration** — automates compilation, timesheet collection, and reminders
- **Manual trigger scripts** — trigger compilation, timesheet collection, or reminders on demand via `docker compose exec`
- **Bundled TaskJuggler documentation** — reference docs are included in the Docker image for enhanced syntax accuracy during chat interactions

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

## LLM Agent Chat

The agent chat provides a conversational interface for managing your TaskJuggler project at `http://localhost:8080/chat`. Powered by a locally-running LLM via LM Studio, it can:

- **Review your project plan** — ask about tasks, resources, timelines, and dependencies in plain language
- **Update tasks and resources** — modify attributes, add new tasks, or adjust dependencies through conversation
- **Write timesheets** — log hours by describing what you worked on; the agent generates valid timesheet syntax
- **Create journal entries** — dictate status updates and decisions that get recorded against tasks
- **Generate reports** — request Gantt charts, resource reports, or custom views without learning report syntax
- **Proactive guidance** — the agent highlights overdue tasks, upcoming milestones, and suggests next steps

All file changes are validated through the tj3 compiler before persisting, and backups are created automatically. Write operations require explicit user confirmation.

### Setup

1. Install [LM Studio](https://lmstudio.ai) 0.2+ on your host machine
2. Load a model (any model supporting tool/function calling works best)
3. Start the LM Studio local server (defaults to `http://localhost:1234/v1`)
4. Configure `TJ_CHAT_LM_STUDIO_URL` in `.env` if using a non-default endpoint

The chat feature includes bundled TaskJuggler reference documentation for enhanced syntax accuracy — the agent references these docs to produce correct TJ constructs beyond what the LLM remembers from training data.

If LM Studio is not running, the reports and admin pages remain fully functional; only the chat feature requires an active LM Studio connection.

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
