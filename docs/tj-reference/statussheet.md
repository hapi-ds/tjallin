# statussheet

The `statussheet` keyword collects status information from resources about their assigned tasks. Unlike timesheets (which record hours worked), status sheets focus on progress reporting and issue tracking.

## Syntax

```tjp
statussheet <resource_id> <date> {
  [task entries...]
}
```

- `<resource_id>` — The ID of the resource providing the status update.
- `<date>` — The reporting date in `YYYY-MM-DD` format.

## Task Entry Syntax

```tjp
task <task_path> {
  status <color> "<headline>" {
    [summary "<text>"]
  }
}
```

### Status Colors

| Color | Meaning |
|-------|---------|
| `green` | On track, no issues |
| `yellow` | Minor issues or risks |
| `red` | Significant problems, blocked, or behind schedule |

## Examples

### Simple status sheet

```tjp
statussheet alice 2024-02-05 {
  task acme.development.backend_api.endpoints {
    status green "REST endpoints on track" {
      summary "Completed 8 of 12 planned endpoints. Remaining 4 are straightforward CRUD operations."
    }
  }
  task acme.development.backend_api.auth {
    status yellow "Auth integration delayed" {
      summary "Waiting for OAuth provider credentials. Using mock auth for now. Expected resolution by Wednesday."
    }
  }
}
```

### Status sheet with multiple tasks

```tjp
statussheet bob 2024-02-05 {
  task acme.development.frontend.components {
    status green "Component library progressing well" {
      summary "Button, Input, Card, and Modal components complete. Starting Dropdown next."
    }
  }
  task acme.development.frontend.layouts {
    status green "Layout work started"
  }
}
```

### Critical status

```tjp
statussheet dave 2024-03-11 {
  task acme.testing.integration_tests {
    status red "Integration tests blocked" {
      summary "Cannot run integration tests due to staging environment outage. DevOps investigating. All other testing paused until resolved."
    }
  }
}
```

## Status Reports

Status sheets feed into `statusreport` output:

```tjp
statusreport WeeklyStatus "Weekly Status" {
  formats html
  headline "Weekly Status Report"
}
```

Or displayed via `taskreport` with journal mode:

```tjp
taskreport StatusOverview "Status Overview" {
  formats html
  columns name, status
  journalmode status_up
  journalattributes headline, author, date, summary, alert
}
```

## Comparison: Timesheet vs Status Sheet

| Aspect | Timesheet | Status Sheet |
|--------|-----------|--------------|
| Primary purpose | Record hours worked | Report progress and issues |
| Contains hours | Yes (`work`) | No |
| Contains status | Optional | Required |
| Frequency | Weekly (typically) | As needed |
| Affects scheduling | Yes (updates remaining effort) | No (informational only) |

## Notes

- Status sheets are informational — they do not affect the scheduler's calculations.
- They are primarily used for generating status reports and tracking issues.
- The `status` color provides a quick visual indicator in reports.
- Status sheets can be submitted at any frequency (daily, weekly, per-milestone).
- Unlike timesheets, status sheets do not require a duration — they represent a point-in-time snapshot.
- Status information from status sheets appears in journal/status reports alongside journal entries.
- Resources should only report on tasks they are allocated to.
