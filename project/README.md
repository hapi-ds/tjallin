# Acme Web Platform — Sample TaskJuggler Project

## Overview

This sample project models a realistic 16-week software development effort for a fictional "Acme Web Platform." It demonstrates TaskJuggler's core capabilities through a working example that compiles without errors and produces meaningful reports immediately.

**What this sample demonstrates:**

- Multi-resource scheduling with different working hours, rates, and vacation periods
- Hierarchical task decomposition across four project phases
- Task dependencies that create a visible critical path
- Resource leveling (overlapping allocations resolved by the scheduler)
- Milestones marking phase boundaries
- Cost tracking with account hierarchies and per-resource rates
- Timesheet integration for tracking actual vs. planned progress
- Multiple report types (Gantt chart, resource usage, task list, cost report)

The project uses Swedish Krona (SEK) as currency, the Europe/Stockholm timezone, and runs from 2024-01-15 for 16 weeks.

---

## File Structure

```
project/
├── project.tjp                    # Main project file (entry point)
├── includes/
│   ├── accounts.tji               # Cost account hierarchy
│   ├── resources.tji              # Team member definitions
│   ├── tasks.tji                  # Task hierarchy and dependencies
│   └── reports.tji                # Report definitions
└── timesheets/
    ├── 2024-W03-alice.tji         # Alice's timesheet for week 3
    ├── 2024-W03-bob.tji           # Bob's timesheet for week 3
    ├── 2024-W04-alice.tji         # Alice's timesheet for week 4
    └── 2024-W04-bob.tji           # Bob's timesheet for week 4
```

---

## File-by-File Explanation

### `project.tjp` — Main Project File

The entry point for TaskJuggler compilation. It defines:

- **Project header**: name (`acme_web`), title ("Acme Web Platform"), start date, and duration
- **Global settings**: timezone, date/number/currency formats, currency (SEK)
- **Tracking configuration**: `now` date and `trackingscenario plan` for timesheet comparison
- **Includes**: pulls in all modular `.tji` files

This file acts as a table of contents — you can see the entire project structure at a glance.

### `includes/accounts.tji` — Cost Accounts

Defines the financial tracking structure:

- **cost** — top-level project costs
  - **dev** — Development (split into backend and frontend)
  - **design** — Design work
  - **qa** — Quality Assurance
  - **mgmt** — Project Management
- **revenue** — Income tracking
  - **contract** — Contract payments

Each task is assigned to a cost account via `chargeset`, and each resource has an hourly rate. Together they produce the cost report showing budget consumption per phase and team.

### `includes/resources.tji` — Resource Definitions

Defines five team members with varying characteristics:

| Resource | Role | Hours | Rate (SEK/h) | Skills | Vacation |
|----------|------|-------|---------------|--------|----------|
| Alice | Senior Developer | 8h/day Mon–Fri | 950 | backend, architecture | Feb 19–23 (Winter Break) |
| Bob | Full-Stack Developer | 8h/day Mon–Fri | 800 | frontend, backend | Mar 25–29 (Easter) |
| Carol | UX Designer | 6h/day Mon–Thu | 750 | design, frontend | None |
| Dave | QA Engineer | 8h/day Mon–Fri | 700 | testing, automation | Apr 1–5 (Spring Break) |
| Eve | Project Manager | 4h/day Mon–Fri | 900 | management | None |

This file demonstrates:
- `workinghours` — custom schedules per resource
- `rate` — hourly cost for financial tracking
- `vacation` — named absence periods
- `chargeset` — default cost account assignment
- Custom `extend resource` attribute for skill sets

### `includes/tasks.tji` — Task Hierarchy

Organizes work into four phases:

1. **Phase 1: Planning** (2 weeks) — Requirements, architecture, wireframes
2. **Phase 2: Development** (6 weeks) — Backend API and Frontend UI in parallel
3. **Phase 3: Testing** (4 weeks) — Unit, integration, performance, and UAT
4. **Phase 4: Deployment** (2 weeks) — Infrastructure, staging, production

Key features demonstrated:
- **Dependencies** (`depends`): tasks that must complete before others can start
- **Milestones**: zero-duration markers at phase boundaries (Planning Complete, Feature Complete, Release Candidate, Go Live)
- **Resource leveling**: Alice is allocated to both "REST Endpoints" and "Authentication" simultaneously — the scheduler resolves this conflict by sequencing them
- **Cross-phase dependencies**: each phase depends on the previous phase's milestone
- **Cost account assignment**: every task has a `chargeset` linking it to the account hierarchy

### `includes/reports.tji` — Report Definitions

Defines four report types:

| Report | Type | Purpose |
|--------|------|---------|
| GanttChart | `taskreport` | Visual timeline with dependencies, milestones, and critical path |
| ResourceUsage | `resourcereport` | Weekly resource allocation and utilization percentages |
| TaskList | `taskreport` | Flat listing with dates, effort, cost, and completion status |
| CostReport | `accountreport` | Financial breakdown by cost account over time |

Also includes reusable macros (`TaskTip`, `ResourceTip`) for tooltip formatting in chart columns.

### `timesheets/` — Timesheet Files

Four sample timesheets showing actual time reported by team members:

- **2024-W03-alice.tji**: 32h on Database Schema (green), 8h on REST Endpoints (yellow)
- **2024-W03-bob.tji**: 40h on Component Library (green)
- **2024-W04-alice.tji**: 30h on REST Endpoints (yellow), 10h on Authentication (yellow)
- **2024-W04-bob.tji**: 32h on Page Layouts (green), 8h on API Integration (yellow)

These demonstrate the `trackingscenario` feature — comparing planned schedule against actual progress.

---

## How to Modify the Sample

### Adding a New Resource

Edit `includes/resources.tji` and add a new resource block:

```tjp
resource frank "Frank" {
  workinghours mon - fri 9:00 - 17:00
  workinghours sat, sun off
  rate 850.0
  Skills "devops, backend"
  chargeset cost.dev.backend
}
```

Then allocate Frank to tasks in `includes/tasks.tji`:

```tjp
task ci_pipeline "CI/CD Pipeline" {
  effort 5d
  allocate frank
  chargeset cost.dev.backend
}
```

### Adding a New Task

Edit `includes/tasks.tji`. Add tasks inside an existing phase or create a new one:

```tjp
task documentation "Documentation" {
  effort 5d
  allocate eve
  depends !staging
  chargeset cost.mgmt
}
```

Key rules:
- Use `effort` for work-based scheduling (scheduler calculates duration from resource availability)
- Use `duration` for calendar-based scheduling (fixed elapsed time)
- Use `depends !taskname` for dependencies within the same parent, or full path (`acme.development.backend.endpoints`) for cross-branch dependencies
- Always assign a `chargeset` for cost tracking

### Changing Project Dates

Edit the project header in `project.tjp`:

```tjp
project acme_web "Acme Web Platform" 2025-03-01 +20w {
  ...
  now 2025-03-15
  ...
}
```

- First date: project start
- `+16w`: project duration (weeks, months, or end date)
- `now`: the "current" date for tracking comparison

### Adding a Vacation

Edit the resource in `includes/resources.tji`:

```tjp
resource alice "Alice" {
  ...
  vacation "Summer" 2024-07-01 - 2024-07-20
}
```

Note: the end date is exclusive (the resource returns on that date).

### Adding a New Report

Edit `includes/reports.tji`:

```tjp
taskreport MilestoneReport "Milestones" {
  formats html
  headline "Project Milestones"
  columns name, start, end, complete
  hidetask ~ismilestone()
  sortmode plan.start.up
}
```

---

## How Timesheets Work

### Timesheet Format

A timesheet reports actual work for one resource over one week:

```tjp
timesheet <resource_id> <week_start_date> +1w {
  task <full.task.path> {
    work <hours>h
    status <color> "Short summary" {
      summary "Detailed description of work done"
    }
  }
}
```

**Status colors:**
- `green` — on track, no issues
- `yellow` — in progress, minor concerns
- `red` — blocked or significantly behind

### File Naming Convention

```
timesheets/YYYY-WNN-resourceid.tji
```

Example: `2024-W03-alice.tji` is Alice's timesheet for calendar week 3 of 2024.

### Submitting Timesheets

Timesheets can be submitted in two ways:

1. **Email**: Send the `.tji` file as an attachment to the configured mail domain. The Mail Service validates and stores it automatically.
2. **Web UI**: Upload through the TaskJuggler web interface at `http://localhost:8080`.

### How Timesheets Are Processed

1. Timesheet files land in the `timesheets/` directory
2. The Cron Service triggers timesheet collection on schedule (default: hourly)
3. On the next project compilation (default: every 15 minutes), TaskJuggler incorporates timesheet data
4. Reports update to show actual progress vs. planned schedule

### Writing a New Timesheet

1. Copy an existing timesheet as a template
2. Update the resource ID, date, and task paths
3. Use full task paths (e.g., `acme.development.backend.endpoints`)
4. Report hours worked and status for each task you touched that week
5. Save to `timesheets/` with the naming convention above

---

## Creating a New Project from Scratch

Use this sample as a template to build your own project:

### Step 1: Copy the Structure

```bash
cp -r project/ my-project/
```

### Step 2: Edit `project.tjp`

Update the project header with your project's name, start date, duration, timezone, and currency:

```tjp
project my_proj "My Project" 2025-01-06 +12w {
  timezone "Europe/Stockholm"
  timeformat "%Y-%m-%d"
  numberformat "-" "" "," "." 1
  currencyformat "(" ")" "," "." 0
  currency "SEK"
  now 2025-01-06
  trackingscenario plan
}
```

### Step 3: Define Your Cost Accounts

Edit `includes/accounts.tji` to match your budget structure. Keep the hierarchy shallow for small projects.

### Step 4: Define Your Resources

Edit `includes/resources.tji`. For each team member, specify:
- Working hours and days
- Hourly rate
- Skills (optional, for allocation matching)
- Known vacations
- Default cost account (`chargeset`)

### Step 5: Define Your Tasks

Edit `includes/tasks.tji`. Start with phases, then decompose into tasks:
- Assign effort or duration to leaf tasks only
- Add dependencies between tasks
- Create milestones at phase boundaries
- Allocate resources to each task
- Assign cost accounts

### Step 6: Configure Reports

Edit `includes/reports.tji`. The four report types in this sample cover most needs. Adjust columns, filters, and time scales to match your project.

### Step 7: Remove Sample Timesheets

Delete the files in `timesheets/` — they reference the sample project's task paths and won't apply to your project.

### Step 8: Update the Docker Configuration

If using the Docker Compose stack, update `.env` to point to your project:

```ini
TJ_PROJECT_PATH=./my-project
TJ_PROJECT_FILE=project.tjp
```

### Step 9: Compile and Verify

Run a compilation to check for errors:

```bash
./scripts/rebuild.sh
```

Or compile directly:

```bash
docker exec tj-core tj3 /app/project/project.tjp
```

Fix any errors reported by `tj3` before proceeding.

---

## TaskJuggler Documentation Links

| Feature | Documentation |
|---------|--------------|
| Project header & properties | https://taskjuggler.org/tj3/manual/project.html |
| Resource definitions | https://taskjuggler.org/tj3/manual/resource.html |
| Task definitions | https://taskjuggler.org/tj3/manual/task.html |
| Dependencies | https://taskjuggler.org/tj3/manual/depends.html |
| Milestones | https://taskjuggler.org/tj3/manual/milestone.html |
| Working hours | https://taskjuggler.org/tj3/manual/workinghours.html |
| Vacations | https://taskjuggler.org/tj3/manual/vacation.html |
| Cost accounts | https://taskjuggler.org/tj3/manual/account.html |
| Reports (taskreport) | https://taskjuggler.org/tj3/manual/taskreport.html |
| Reports (resourcereport) | https://taskjuggler.org/tj3/manual/resourcereport.html |
| Reports (accountreport) | https://taskjuggler.org/tj3/manual/accountreport.html |
| Timesheets | https://taskjuggler.org/tj3/manual/timesheet.html |
| Include files | https://taskjuggler.org/tj3/manual/include.html |
| Macros | https://taskjuggler.org/tj3/manual/macro.html |
| Rich text (tooltips) | https://taskjuggler.org/tj3/manual/richtext.html |
| Complete reference | https://taskjuggler.org/tj3/manual/index.html |
