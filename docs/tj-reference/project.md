# project

The `project` declaration is the top-level container for every TaskJuggler project. It defines the project ID, name, time boundaries, and global settings such as timezone, currency, and date formats.

## Syntax

```tjp
project <id> "<name>" <start_date> <end_spec> {
  [attributes...]
}
```

- `<id>` — A unique identifier (alphanumeric + underscores, no spaces).
- `<name>` — A human-readable project name (quoted string).
- `<start_date>` — Project start date in `YYYY-MM-DD` format.
- `<end_spec>` — Either an absolute end date (`YYYY-MM-DD`) or a relative duration (`+<N>w`, `+<N>m`, `+<N>y`).

## Attributes

| Attribute | Description | Example |
|-----------|-------------|---------|
| `timezone` | IANA timezone for all date calculations | `timezone "Europe/Stockholm"` |
| `timeformat` | Default date display format (strftime) | `timeformat "%Y-%m-%d"` |
| `shorttimeformat` | Short date format for compact displays | `shorttimeformat "%d.%m"` |
| `numberformat` | Number formatting: negative prefix, negative suffix, thousands separator, fraction separator, fraction digits | `numberformat "-" "" "," "." 1` |
| `currencyformat` | Currency formatting (same structure as numberformat) | `currencyformat "(" ")" "," "." 0` |
| `currency` | Currency symbol/code | `currency "SEK"` |
| `now` | Override the current date for scheduling calculations | `now 2024-02-05` |
| `trackingscenario` | Scenario used for tracking actual progress | `trackingscenario plan` |
| `workinghours` | Default working hours for all resources | `workinghours mon - fri 9:00 - 17:00` |
| `dailyworkinghours` | Hours per working day (used for effort conversion) | `dailyworkinghours 8` |
| `yearlyworkingdays` | Working days per year (used for effort conversion) | `yearlyworkingdays 260.714` |
| `timingresolution` | Minimum scheduling granularity | `timingresolution 60min` |
| `weekstartsmonday` | Whether weeks start on Monday (default: yes) | `weekstartsmonday yes` |
| `scenario` | Define named scenarios for what-if analysis | `scenario plan "Plan" { ... }` |
| `extend` | Add custom attributes to tasks, resources, or accounts | `extend task { ... }` |

## Duration Suffixes

| Suffix | Meaning |
|--------|---------|
| `min` | Minutes |
| `h` | Hours |
| `d` | Days (working days) |
| `w` | Weeks |
| `m` | Months |
| `y` | Years |

## Examples

### Minimal project

```tjp
project myproject "My Project" 2024-01-01 +12w {
}
```

### Full project with settings

```tjp
project acme_web "Acme Web Platform" 2024-01-15 +26w {
  timezone "Europe/Stockholm"
  timeformat "%Y-%m-%d"
  numberformat "-" "" "," "." 1
  currencyformat "(" ")" "," "." 0
  currency "SEK"
  now 2024-02-05
  trackingscenario plan
}
```

### Project with scenarios

```tjp
project demo "Demo Project" 2024-01-01 +6m {
  timezone "US/Eastern"
  scenario plan "Plan" {
    scenario optimistic "Optimistic"
    scenario pessimistic "Pessimistic"
  }
}
```

## Notes

- The `project` declaration must appear before any other declarations (tasks, resources, etc.).
- The `now` attribute is critical for overdue detection and progress tracking — it defines what "today" means for the scheduler.
- Use `include` statements after the project block to organize large projects into separate files.
- The `trackingscenario` attribute specifies which scenario is used for actual progress tracking (timesheets, completion).
