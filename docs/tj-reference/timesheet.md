# timesheet

The `timesheet` keyword records actual hours worked by a resource during a specific time period. Timesheets are the primary mechanism for tracking progress against the plan.

## Syntax

```tjp
timesheet <resource_id> <start_date> <duration> {
  [task entries...]
}
```

- `<resource_id>` — The ID of the resource reporting time.
- `<start_date>` — Start date of the reporting period (YYYY-MM-DD, typically a Monday).
- `<duration>` — Period length, typically `+1w` for weekly timesheets.

## Task Entry Syntax

```tjp
task <task_path> {
  work <hours>h
  [remaining <hours>h]
  [end <date>]
  [status <color> "<headline>" [{summary "<text>"}]]
}
```

### Task Entry Attributes

| Attribute | Description | Example |
|-----------|-------------|---------|
| `work` | Hours worked on this task during the period | `work 32h` |
| `remaining` | Estimated remaining effort | `remaining 16h` |
| `end` | Actual or expected end date | `end 2024-02-15` |
| `status` | Status indicator with color and headline | `status green "On track"` |

### Status Colors

| Color | Meaning |
|-------|---------|
| `green` | On track, no issues |
| `yellow` | Minor issues or risks |
| `red` | Significant problems, needs attention |

### Status Syntax

```tjp
status <color> "<headline>" {
  summary "<detailed_text>"
}
```

Or without summary:

```tjp
status <color> "<headline>"
```

## File Naming Convention

Timesheet files follow the pattern:

```
YYYY-Www-<resource_id>.tji
```

- `YYYY` — ISO year
- `Www` — ISO week number (zero-padded, e.g., `W03`)
- `<resource_id>` — Resource identifier

Examples: `2024-W03-alice.tji`, `2024-W04-bob.tji`

## Examples

### Simple timesheet

```tjp
timesheet alice 2024-01-29 +1w {
  task acme.development.backend_api.schema {
    work 40h
    status green "Completed"
  }
}
```

### Multiple task entries

```tjp
timesheet alice 2024-01-29 +1w {
  task acme.development.backend_api.schema {
    work 32h
    status green "Schema design completed" {
      summary "Finalized database schema for all core entities including users, sessions, and content tables."
    }
  }
  task acme.development.backend_api.endpoints {
    work 8h
    status yellow "Started endpoint scaffolding" {
      summary "Set up project structure and implemented initial CRUD routes for user entity."
    }
  }
}
```

### Timesheet with remaining effort

```tjp
timesheet bob 2024-02-05 +1w {
  task acme.development.frontend.components {
    work 24h
    remaining 40h
    status yellow "In progress" {
      summary "Completed button, input, and card components. Still need modal, dropdown, and table."
    }
  }
  task acme.development.frontend.layouts {
    work 16h
    remaining 24h
    status green "Started layouts"
  }
}
```

### Timesheet with end date

```tjp
timesheet dave 2024-03-04 +1w {
  task acme.testing.unit_tests {
    work 40h
    end 2024-03-08
    status green "Unit tests complete" {
      summary "All unit tests written and passing. 95% code coverage achieved."
    }
  }
}
```

## Merging Timesheets

When a timesheet file already exists for a resource and week, new entries should be merged:

- Replace any existing entry for the same task path with the new entry.
- Preserve all entries for other task paths.
- Maintain the overall `timesheet` block structure.

## Notes

- Task paths in timesheets must reference existing tasks in the project plan.
- The `work` value represents actual hours worked, not planned effort.
- Total `work` hours across all task entries should not exceed the resource's weekly working capacity.
- Timesheets are typically stored in a dedicated `timesheets/` directory.
- The `trackingscenario` in the project declaration determines which scenario timesheets apply to.
- Timesheets are included in the project via `include` statements or directory-level includes.
- The `remaining` attribute helps the scheduler re-estimate task completion dates.
- Status entries appear in journal/status reports and provide visibility into progress.
