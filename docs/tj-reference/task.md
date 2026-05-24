# task

The `task` keyword defines a unit of work in the project schedule. Tasks can be nested to form a work breakdown structure (WBS). Leaf tasks have effort or duration; container tasks derive their schedule from children.

## Syntax

```tjp
task <id> "<name>" {
  [attributes...]
  [nested tasks...]
}
```

- `<id>` — Unique identifier within the parent scope (alphanumeric + underscores).
- `<name>` — Human-readable task name (quoted string).

## Task Paths

Tasks are referenced by their dotted path from the project root:

```
project_id.phase.subphase.leaf_task
```

Within a task body, relative references use `!` prefix for siblings:

```tjp
depends !sibling_task
depends parent.sibling.child
```

## Attributes

| Attribute | Description | Example |
|-----------|-------------|---------|
| `effort` | Work effort required (scheduled across allocated resources) | `effort 10d` |
| `duration` | Calendar duration (regardless of resource availability) | `duration 5d` |
| `length` | Working-time duration (excludes non-working days) | `length 5d` |
| `milestone` | Marks task as a zero-duration milestone | `milestone` |
| `allocate` | Assign one or more resources | `allocate alice` |
| `depends` | Task dependencies (finish-to-start by default) | `depends !requirements` |
| `precedes` | Reverse dependency (this task must finish before target starts) | `precedes !deployment` |
| `start` | Fixed start date | `start 2024-03-01` |
| `end` | Fixed end date | `end 2024-03-15` |
| `maxstart` | Latest allowed start date | `maxstart 2024-03-01` |
| `maxend` | Latest allowed end date | `maxend 2024-06-30` |
| `minstart` | Earliest allowed start date | `minstart 2024-02-01` |
| `minend` | Earliest allowed end date | `minend 2024-04-01` |
| `priority` | Scheduling priority (1–1000, default 500) | `priority 800` |
| `complete` | Percentage complete (0–100) | `complete 75` |
| `responsible` | Resource responsible for the task | `responsible eve` |
| `chargeset` | Cost account for this task's costs | `chargeset backend` |
| `charge` | One-time or per-unit charge | `charge 5000 onstart` |
| `note` | Descriptive note (rich text) | `note "Implementation details..."` |
| `journalentry` | Inline journal entry (see journalentry.md) | See below |
| `flags` | Custom flags for filtering | `flags team_a, critical` |
| `limits` | Resource usage limits | `limits { dailymax 4h }` |
| `booking` | Record actual work done | `booking alice 2024-01-15 +1d { ... }` |
| `scheduled` | Mark task as fully scheduled (no auto-scheduling) | `scheduled` |
| `scheduling` | Scheduling direction | `scheduling asap` or `scheduling alap` |
| `shift` | Apply a shift pattern | `shift night_shift` |
| `purge` | Clear inherited attributes | `purge allocate` |

## Dependency Syntax

```tjp
depends <task_path> [{gapduration <dur>} | {gaplength <dur>}]
```

Dependency types via attributes:

- **Finish-to-Start** (default): predecessor must finish before this starts
- **Start-to-Start**: `depends <path> { onstart }` 
- **Finish-to-Finish**: `depends <path> { onend }`

Multiple dependencies:

```tjp
depends !task_a, !task_b, parent.other_task
```

## Effort Units

| Unit | Meaning |
|------|---------|
| `min` | Minutes |
| `h` | Hours |
| `d` | Working days |
| `w` | Working weeks |
| `m` | Working months |
| `y` | Working years |

## Examples

### Simple leaf task

```tjp
task schema "Database Schema" {
  effort 5d
  allocate alice
  chargeset backend
}
```

### Task with dependencies

```tjp
task endpoints "REST Endpoints" {
  effort 15d
  allocate alice
  allocate bob
  depends !schema
  chargeset backend
}
```

### Milestone

```tjp
task planning_complete "Planning Complete" {
  milestone
  depends !requirements, !architecture, !wireframes
}
```

### Hierarchical task structure

```tjp
task development "Phase 2: Development" {
  depends !planning.planning_complete

  task backend_api "Backend API" {
    task schema "Database Schema" {
      effort 5d
      allocate alice
    }
    task endpoints "REST Endpoints" {
      effort 15d
      allocate alice
      allocate bob
      depends !schema
    }
  }

  task frontend "Frontend UI" {
    task components "Component Library" {
      effort 10d
      allocate bob
      allocate carol
    }
    task integration "API Integration" {
      effort 10d
      allocate bob
      depends !components
      depends development.backend_api.endpoints
    }
  }

  task feature_complete "Feature Complete" {
    milestone
    depends !backend_api, !frontend
  }
}
```

### Task with priority and limits

```tjp
task critical_fix "Critical Bug Fix" {
  effort 2d
  allocate alice
  priority 900
  limits { dailymax 8h }
}
```

## Notes

- Container tasks (those with child tasks) cannot have `effort` or `duration` — their schedule is derived from children.
- The `!` prefix in dependency paths means "sibling of the current task" (relative reference within the same parent).
- Multiple `allocate` lines assign multiple resources; effort is split among them.
- `effort` schedules work across available resource hours; `duration` is fixed calendar time regardless of resource availability.
- `length` is like duration but only counts working days.
- Tasks without `effort`, `duration`, `length`, or `milestone` and without children will cause a compiler warning.
