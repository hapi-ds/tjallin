# report

TaskJuggler supports several report types for visualizing project data. Each report type is a top-level keyword that generates output in HTML, CSV, or other formats.

## Report Types

| Type | Description |
|------|-------------|
| `taskreport` | Task-centric report (Gantt charts, task lists) |
| `resourcereport` | Resource-centric report (utilization, allocation) |
| `accountreport` | Financial report by cost account |
| `textreport` | Free-form text/HTML report |
| `statusreport` | Status report based on journal entries |

## Syntax

```tjp
<report_type> <id> "<title>" {
  [attributes...]
}
```

- `<report_type>` — One of: `taskreport`, `resourcereport`, `accountreport`, `textreport`, `statusreport`
- `<id>` — Unique report identifier (alphanumeric + underscores).
- `<title>` — Report title (quoted string), used as the page heading.

## Common Attributes

| Attribute | Description | Example |
|-----------|-------------|---------|
| `formats` | Output format(s) | `formats html` or `formats html, csv` |
| `headline` | Report headline/title | `headline "Project Gantt Chart"` |
| `columns` | Column definitions | `columns bsi, name, start, end, effort, chart` |
| `timeformat` | Date format in report output | `timeformat "%Y-%m-%d"` |
| `loadunit` | Unit for effort display | `loadunit days` or `loadunit hours` |
| `sorttasks` | Task sort order | `sorttasks plan.start.up` |
| `sortresources` | Resource sort order | `sortresources name.up` |
| `hidetask` | Expression to hide tasks | `hidetask ~isleaf()` |
| `hideresource` | Expression to hide resources | `hideresource @all` |
| `rolluptask` | Expression to roll up tasks | `rolluptask isleaf()` |
| `rollupresource` | Expression to roll up resources | `rollupresource isleaf()` |
| `caption` | Report caption/description | `caption "Schedule overview"` |
| `period` | Restrict report to a time period | `period 2024-01-01 - 2024-06-30` |
| `start` | Report start date | `start 2024-01-01` |
| `end` | Report end date | `end 2024-06-30` |
| `taskroot` | Root task for the report | `taskroot acme.development` |
| `resourceroot` | Root resource for the report | `resourceroot dev_team` |
| `journalmode` | Journal display mode | `journalmode journal` |
| `journalattributes` | Which journal fields to show | `journalattributes headline, author, date, summary` |
| `left` | Left header content | `left "Company Logo"` |
| `center` | Center header content | `center "Project Report"` |
| `right` | Right header content | `right "<-query attribute='now'->"` |
| `width` | Report width | `width 1000` |
| `height` | Report height | `height 600` |

## Load Units

| Value | Description |
|-------|-------------|
| `minutes` | Display effort in minutes |
| `hours` | Display effort in hours |
| `days` | Display effort in working days |
| `weeks` | Display effort in working weeks |
| `months` | Display effort in working months |
| `shortauto` | Automatic short format |
| `longauto` | Automatic long format |

## Sort Orders

Format: `<attribute>.<direction>`

Directions: `up` (ascending), `down` (descending)

Common sort attributes:
- `plan.start` — Planned start date
- `plan.end` — Planned end date
- `plan.effort` — Planned effort
- `name` — Alphabetical by name
- `id` — By identifier
- `bsi` — By WBS index

## Filter Expressions

Used in `hidetask`, `hideresource`, `rolluptask`, `rollupresource`:

| Expression | Description |
|------------|-------------|
| `isleaf()` | True for leaf tasks/resources (no children) |
| `iscontainer()` | True for container tasks/resources |
| `ismilestone()` | True for milestone tasks |
| `istask()` | True for task rows |
| `isresource()` | True for resource rows |
| `isvalid(plan.effort)` | True if attribute has a value |
| `@all` | Matches everything |
| `~expr` | Negation (NOT) |
| `expr & expr` | Logical AND |
| `expr | expr` | Logical OR |

## Examples

### Gantt Chart (taskreport)

```tjp
taskreport GanttChart "Gantt Chart" {
  formats html
  headline "Project Gantt Chart"
  columns bsi { title "WBS" },
         name,
         start { title "Start" },
         end { title "End" },
         effort,
         duration,
         chart { scale week width 800 }
  timeformat "%Y-%m-%d"
  loadunit days
  hideresource @all
  caption "Project schedule with dependencies and milestones."
}
```

### Resource Utilization (resourcereport)

```tjp
resourcereport ResourceUsage "Resource Usage" {
  formats html
  headline "Resource Utilization"
  columns no,
         name,
         effort,
         weekly { width 800 }
  timeformat "%Y-%m-%d"
  loadunit hours
  hidetask ~(isleaf() & isvalid(plan.effort))
  caption "Weekly resource allocation."
}
```

### Cost Report (accountreport)

```tjp
accountreport CostReport "Cost Report" {
  formats html
  headline "Financial Summary"
  columns no, name, cost, weekly
  timeformat "%Y-%m-%d"
  caption "Financial breakdown by cost account."
}
```

### Status Report (statusreport)

```tjp
statusreport StatusReport "Weekly Status" {
  formats html
  headline "Weekly Status Report"
  period %{2024-01-29} - %{2024-02-05}
}
```

### Text Report (textreport)

```tjp
textreport Overview "Project Overview" {
  formats html
  headline "Project Overview"
  center -8<-
    This is a custom text report with embedded queries.
    Project: <-query attribute='name'->
    Start: <-query attribute='start'->
    End: <-query attribute='end'->
  ->8-
}
```

### Journal Report

```tjp
taskreport JournalReport "Project Journal" {
  formats html
  headline "Project Journal"
  columns name, journal
  journalmode journal
  journalattributes headline, author, date, summary
}
```

## Column Modifiers

Columns can have inline modifiers:

```tjp
columns name { title "Task Name" width 200 },
       start { title "Start Date" },
       chart { scale week width 800 tooltip ... }
```

See `columns.md` for the full list of standard column identifiers.

## Notes

- Reports are typically placed in a dedicated include file (e.g., `reports.tji`).
- The `formats html` attribute generates an HTML file named after the report ID.
- Multiple formats can be specified: `formats html, csv`.
- Use `taskroot` to limit a report to a subtree of the project.
- The `chart` column renders a Gantt bar chart and is only available in `taskreport`.
- Use macros to define reusable tooltip content for chart columns.
- Reports without `hideresource @all` will show resource rows under each task.
