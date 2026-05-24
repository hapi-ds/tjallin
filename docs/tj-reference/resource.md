# resource

The `resource` keyword defines a person, team, or equipment that can be allocated to tasks. Resources have working hours, rates, vacations, and can be nested to form teams.

## Syntax

```tjp
resource <id> "<name>" {
  [attributes...]
  [nested resources...]
}
```

- `<id>` — Unique identifier (alphanumeric + underscores).
- `<name>` — Human-readable display name (quoted string).

## Attributes

| Attribute | Description | Example |
|-----------|-------------|---------|
| `workinghours` | Define working schedule per day | `workinghours mon - fri 9:00 - 17:00` |
| `rate` | Cost rate per working day | `rate 950.0` |
| `overtime` | Overtime rate multiplier | `overtime 1.5` |
| `vacation` | Define vacation/absence periods | `vacation "Holiday" 2024-12-23 - 2024-12-28` |
| `shift` | Apply a named shift pattern | `shift night_shift` |
| `efficiency` | Resource efficiency factor (0.0–2.0, default 1.0) | `efficiency 0.8` |
| `limits` | Usage limits for this resource | `limits { dailymax 6h weeklymax 30h }` |
| `flags` | Custom flags for filtering | `flags senior, backend` |
| `email` | Email address (used in reports) | `email "alice@example.com"` |
| `managers` | Manager resource(s) | `managers eve` |
| `leaves` | Alternative to vacation for defining absences | `leaves holiday 2024-12-25` |
| `purge` | Clear inherited attributes | `purge workinghours` |

## Working Hours Syntax

```tjp
workinghours <day_spec> <time_range | off>
```

Day specifications:
- Single day: `mon`, `tue`, `wed`, `thu`, `fri`, `sat`, `sun`
- Day range: `mon - fri`
- Multiple days: `sat, sun`

Time ranges:
- `9:00 - 17:00` — Working from 9 AM to 5 PM
- `9:00 - 12:00, 13:00 - 17:00` — With lunch break
- `off` — No working hours on these days

## Vacation Syntax

```tjp
vacation "<name>" <start_date> - <end_date>
```

- Dates are in `YYYY-MM-DD` format.
- The end date is exclusive (the resource returns on that date).

## Examples

### Full-time resource

```tjp
resource alice "Alice" {
  workinghours mon - fri 9:00 - 17:00
  workinghours sat, sun off
  rate 950.0
  vacation "Winter Break" 2024-02-19 - 2024-02-24
}
```

### Part-time resource

```tjp
resource carol "Carol" {
  workinghours mon - thu 9:00 - 15:00
  workinghours fri, sat, sun off
  rate 750.0
}
```

### Resource with efficiency

```tjp
resource intern "Intern" {
  workinghours mon - fri 9:00 - 17:00
  workinghours sat, sun off
  rate 300.0
  efficiency 0.5
}
```

### Team hierarchy

```tjp
resource dev_team "Development Team" {
  resource alice "Alice" {
    workinghours mon - fri 9:00 - 17:00
    rate 950.0
  }
  resource bob "Bob" {
    workinghours mon - fri 9:00 - 17:00
    rate 800.0
  }
}
```

### Resource with limits

```tjp
resource consultant "External Consultant" {
  workinghours mon - fri 9:00 - 17:00
  rate 1500.0
  limits { weeklymax 20h }
}
```

### Resource with multiple vacations

```tjp
resource dave "Dave" {
  workinghours mon - fri 9:00 - 17:00
  workinghours sat, sun off
  rate 700.0
  vacation "Spring Break" 2024-04-01 - 2024-04-06
  vacation "Summer" 2024-07-01 - 2024-07-15
  vacation "Christmas" 2024-12-23 - 2024-12-28
}
```

## Notes

- Working hours default to the project-level `workinghours` if not specified on the resource.
- Nested resources inherit the parent's working hours and can override them.
- When a resource is allocated to a task, the scheduler uses the resource's working hours to determine availability.
- The `rate` attribute defines cost per working day and is used in cost calculations and account reports.
- Resources can be allocated to multiple tasks; the scheduler resolves conflicts based on task priority and dependencies.
- Use `limits` to cap how much a resource can work per day/week, preventing over-allocation.
