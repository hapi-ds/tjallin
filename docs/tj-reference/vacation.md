# vacation

The `vacation` keyword defines periods when a resource (or all resources) is unavailable for work. Vacations can be declared at the project level (global) or within individual resource definitions.

## Syntax

### Within a resource

```tjp
resource alice "Alice" {
  vacation "<name>" <start_date> - <end_date>
}
```

### Global (project-level) vacation

```tjp
vacation "<name>" <start_date> - <end_date>
```

- `<name>` — Human-readable vacation name (quoted string).
- `<start_date>` — First day of vacation (YYYY-MM-DD).
- `<end_date>` — Day the resource returns (exclusive, YYYY-MM-DD).

## Examples

### Resource vacation

```tjp
resource alice "Alice" {
  workinghours mon - fri 9:00 - 17:00
  rate 950.0
  vacation "Winter Break" 2024-02-19 - 2024-02-24
  vacation "Summer Holiday" 2024-07-01 - 2024-07-22
}
```

### Multiple vacations

```tjp
resource dave "Dave" {
  workinghours mon - fri 9:00 - 17:00
  rate 700.0
  vacation "Spring Break" 2024-04-01 - 2024-04-06
  vacation "Summer" 2024-07-15 - 2024-08-05
  vacation "Christmas" 2024-12-23 - 2024-12-28
}
```

### Global holidays (apply to all resources)

```tjp
project myproject "My Project" 2024-01-01 +12m {
  timezone "Europe/Stockholm"
}

# These apply to all resources in the project
vacation "New Year's Day" 2024-01-01 - 2024-01-02
vacation "Epiphany" 2024-01-06 - 2024-01-07
vacation "Good Friday" 2024-03-29 - 2024-03-30
vacation "Easter Monday" 2024-04-01 - 2024-04-02
vacation "May Day" 2024-05-01 - 2024-05-02
vacation "National Day" 2024-06-06 - 2024-06-07
vacation "Midsummer" 2024-06-21 - 2024-06-22
vacation "Christmas Eve" 2024-12-24 - 2024-12-25
vacation "Christmas Day" 2024-12-25 - 2024-12-26
vacation "Boxing Day" 2024-12-26 - 2024-12-27
```

### Single-day vacation

```tjp
vacation "Company Day" 2024-05-15 - 2024-05-16
```

## Leaves (Alternative Syntax)

The `leaves` keyword provides an alternative way to define absences with categorization:

```tjp
resource alice "Alice" {
  leaves annual 2024-07-01 - 2024-07-15
  leaves sick 2024-02-10 - 2024-02-12
  leaves special 2024-03-20 - 2024-03-21
  leaves holiday 2024-12-25
}
```

### Leave Types

| Type | Description |
|------|-------------|
| `annual` | Annual leave / vacation |
| `sick` | Sick leave |
| `special` | Special leave (e.g., bereavement, moving) |
| `holiday` | Public holiday |
| `unpaid` | Unpaid leave |

## Notes

- The end date is exclusive — the resource is available again on that date.
- Global vacations (defined outside any resource block) apply to all resources.
- Resource-level vacations only apply to that specific resource.
- The scheduler automatically accounts for vacations when calculating task schedules.
- Vacations affect effort-based scheduling: a 5-day task allocated to a resource with 2 vacation days in the period will take 7 calendar days.
- Vacation periods cannot overlap with each other for the same resource.
- Use global vacations for public holidays that affect the entire team.
- Use resource-level vacations for individual time off.
