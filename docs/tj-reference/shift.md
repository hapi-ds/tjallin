# shift

The `shift` keyword defines named working-hour patterns that can be applied to resources or tasks. Shifts allow modeling of non-standard schedules like night shifts, rotating schedules, or seasonal working patterns.

## Syntax

```tjp
shift <id> "<name>" {
  [attributes...]
}
```

- `<id>` — Unique identifier (alphanumeric + underscores).
- `<name>` — Human-readable shift name (quoted string).

## Attributes

| Attribute | Description | Example |
|-----------|-------------|---------|
| `workinghours` | Working hours for specific days | `workinghours mon - fri 22:00 - 06:00` |
| `vacation` | Vacation/non-working periods within the shift | `vacation 2024-12-25` |
| `replace` | Whether this shift replaces or supplements the resource's default hours | `replace` |

## Applying Shifts

### To a resource

```tjp
resource night_guard "Night Guard" {
  shift night_shift
}
```

### To a resource for a specific period

```tjp
resource alice "Alice" {
  workinghours mon - fri 9:00 - 17:00
  shift night_shift 2024-03-01 - 2024-03-31
}
```

### To a task

```tjp
task maintenance "Nightly Maintenance" {
  shift night_shift
  effort 5d
  allocate ops_team
}
```

## Examples

### Night shift

```tjp
shift night_shift "Night Shift" {
  workinghours mon - fri 22:00 - 06:00
  workinghours sat, sun off
}
```

### Morning shift

```tjp
shift morning_shift "Morning Shift" {
  workinghours mon - fri 6:00 - 14:00
  workinghours sat, sun off
}
```

### Afternoon shift

```tjp
shift afternoon_shift "Afternoon Shift" {
  workinghours mon - fri 14:00 - 22:00
  workinghours sat, sun off
}
```

### Weekend shift

```tjp
shift weekend_shift "Weekend Shift" {
  workinghours mon - fri off
  workinghours sat, sun 8:00 - 16:00
}
```

### Part-time shift

```tjp
shift part_time "Part Time" {
  workinghours mon, wed, fri 9:00 - 13:00
  workinghours tue, thu, sat, sun off
}
```

### Shift with vacation

```tjp
shift factory_shift "Factory Shift" {
  workinghours mon - fri 7:00 - 15:00
  workinghours sat, sun off
  vacation "Plant Shutdown" 2024-08-01 - 2024-08-15
}
```

### Rotating shifts applied to resources

```tjp
shift early "Early Shift" {
  workinghours mon - fri 6:00 - 14:00
}

shift late "Late Shift" {
  workinghours mon - fri 14:00 - 22:00
}

resource operator_a "Operator A" {
  shift early 2024-01-01 - 2024-01-15
  shift late 2024-01-15 - 2024-02-01
}
```

## Notes

- Shifts override the resource's default working hours for the period they are active.
- If no period is specified when applying a shift, it applies for the entire project duration.
- Shifts must be defined before they are referenced by resources or tasks.
- The `workinghours` syntax within shifts is identical to that used in `resource` and `project` blocks.
- Shifts are useful for modeling 24/7 operations, factory schedules, or temporary schedule changes.
- Multiple shifts can be applied to a resource for different time periods (non-overlapping).
- When a shift is applied to a task, it affects scheduling of that task regardless of the resource's normal hours.
