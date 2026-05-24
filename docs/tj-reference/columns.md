# columns

Column identifiers define what data appears in TaskJuggler reports. Different report types support different columns. This reference covers all standard column identifiers available in TaskJuggler 3.x.

## Syntax

Columns are specified in the `columns` attribute of a report:

```tjp
columns <col1>, <col2>, <col3>, ...
```

Each column can have optional modifiers:

```tjp
columns name { title "Custom Title" width 200 },
       start { title "Start Date" },
       chart { scale week width 800 }
```

## Column Modifiers

| Modifier | Description | Example |
|----------|-------------|---------|
| `title` | Custom column header | `title "Task Name"` |
| `width` | Column width in pixels | `width 200` |
| `scale` | Time scale for chart/calendar columns | `scale week` |
| `tooltip` | Tooltip content (rich text) | `tooltip istask() -8<- ... ->8-` |
| `listtype` | List display type | `listtype bullets` |
| `listitem` | Custom list item format | `listitem "<query ...>"` |
| `start` | Column start date | `start 2024-01-01` |
| `end` | Column end date | `end 2024-06-30` |
| `period` | Column time period | `period 2024-Q1` |

## Standard Column Identifiers

### Task Columns

| Column | Description | Report Types |
|--------|-------------|--------------|
| `bsi` | Work Breakdown Structure Index (e.g., 1.2.3) | taskreport |
| `name` | Task/resource/account name | all |
| `id` | Task/resource identifier | all |
| `start` | Planned start date | taskreport, resourcereport |
| `end` | Planned end date | taskreport, resourcereport |
| `effort` | Planned effort | taskreport, resourcereport |
| `duration` | Calendar duration | taskreport |
| `length` | Working-time duration | taskreport |
| `complete` | Completion percentage (0–100) | taskreport |
| `completed` | Completed effort | taskreport |
| `remaining` | Remaining effort | taskreport |
| `status` | Task status (from timesheets/status sheets) | taskreport |
| `priority` | Task priority | taskreport |
| `responsible` | Responsible resource | taskreport |
| `resources` | Allocated resources | taskreport |
| `depends` | Task dependencies | taskreport |
| `precedes` | Tasks that depend on this task | taskreport |
| `followers` | Following tasks | taskreport |
| `predecessors` | Predecessor tasks | taskreport |
| `flags` | Task flags | taskreport |
| `note` | Task notes | taskreport |
| `inputs` | Input deliverables | taskreport |
| `outputs` | Output deliverables | taskreport |

### Resource Columns

| Column | Description | Report Types |
|--------|-------------|--------------|
| `name` | Resource name | resourcereport |
| `id` | Resource identifier | resourcereport |
| `effort` | Total effort allocated | resourcereport |
| `freeload` | Unallocated time | resourcereport |
| `freetime` | Free time available | resourcereport |
| `rate` | Resource rate | resourcereport |
| `email` | Resource email | resourcereport |
| `managers` | Manager resources | resourcereport |
| `efficiency` | Resource efficiency | resourcereport |

### Financial Columns

| Column | Description | Report Types |
|--------|-------------|--------------|
| `cost` | Total cost | taskreport, accountreport |
| `revenue` | Total revenue | taskreport, accountreport |
| `profit` | Revenue minus cost | accountreport |
| `balance` | Running balance | accountreport |

### Time-Based Columns

| Column | Description | Report Types |
|--------|-------------|--------------|
| `chart` | Gantt chart bar | taskreport |
| `daily` | Daily breakdown | taskreport, resourcereport |
| `weekly` | Weekly breakdown | taskreport, resourcereport, accountreport |
| `monthly` | Monthly breakdown | taskreport, resourcereport, accountreport |
| `quarterly` | Quarterly breakdown | taskreport, resourcereport, accountreport |
| `yearly` | Yearly breakdown | taskreport, resourcereport, accountreport |
| `calendar` | Calendar view | resourcereport |

### Journal Columns

| Column | Description | Report Types |
|--------|-------------|--------------|
| `journal` | Journal entries | taskreport (with journalmode) |
| `journal_sub` | Journal entries including subtasks | taskreport |
| `alert` | Alert level | taskreport |
| `alerttrend` | Alert trend (improving/worsening) | taskreport |

### Numbering Columns

| Column | Description | Report Types |
|--------|-------------|--------------|
| `no` | Sequential row number | all |
| `bsi` | WBS index | taskreport |
| `index` | Hierarchical index | all |
| `line` | Line number | all |
| `hierarchyno` | Hierarchy number | all |

## Chart Column Options

The `chart` column supports additional modifiers:

```tjp
chart {
  scale <timescale>
  width <pixels>
  tooltip <expression> -8<- <content> ->8-
}
```

### Time Scales

| Scale | Description |
|-------|-------------|
| `hour` | Hourly resolution |
| `day` | Daily resolution |
| `week` | Weekly resolution |
| `month` | Monthly resolution |
| `quarter` | Quarterly resolution |
| `year` | Yearly resolution |

## Examples

### Task list with key metrics

```tjp
columns bsi { title "WBS" },
       name,
       start { title "Start" },
       end { title "End" },
       effort,
       cost,
       complete,
       status { width 150 }
```

### Gantt chart columns

```tjp
columns bsi { title "WBS" },
       name,
       start { title "Start" },
       end { title "End" },
       effort,
       duration,
       chart { scale week width 800 }
```

### Resource utilization columns

```tjp
columns no,
       name,
       effort,
       weekly { width 800 }
```

### Financial report columns

```tjp
columns no,
       name,
       cost,
       revenue,
       profit,
       monthly
```

### Minimal task list

```tjp
columns name, start, end, effort, complete
```

### Detailed task list with dependencies

```tjp
columns bsi,
       name { width 250 },
       start,
       end,
       effort,
       resources,
       depends,
       complete,
       status
```

## Notes

- Not all columns are available in all report types — use task columns in `taskreport`, resource columns in `resourcereport`, etc.
- The `chart` column is only available in `taskreport` and renders a visual Gantt bar.
- Time-based columns (`daily`, `weekly`, `monthly`) show effort/cost broken down by period.
- Column order in the `columns` attribute determines display order in the report.
- Use `title` modifier to provide user-friendly column headers.
- The `width` modifier is in pixels and affects HTML output.
- The `no` column provides simple sequential numbering; `bsi` provides WBS-style numbering.
- Columns with tooltips show hover information in HTML reports.
