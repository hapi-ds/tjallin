# include

The `include` statement loads external TaskJuggler files into the current project. This enables modular project organization by splitting definitions across multiple files.

## Syntax

```tjp
include "<file_path>"
```

- `<file_path>` — Relative path to the file to include (quoted string).

## File Extensions

| Extension | Description |
|-----------|-------------|
| `.tjp` | Main project file (contains the `project` declaration) |
| `.tji` | Include file (contains tasks, resources, reports, etc.) |

## Examples

### Standard project structure

```tjp
project acme "Acme Project" 2024-01-15 +26w {
  timezone "Europe/Stockholm"
  now 2024-02-05
}

include "includes/accounts.tji"
include "includes/resources.tji"
include "includes/tasks.tji"
include "includes/reports.tji"
```

### Including timesheets

```tjp
include "timesheets/2024-W03-alice.tji"
include "timesheets/2024-W03-bob.tji"
include "timesheets/2024-W04-alice.tji"
```

### Conditional includes (using macros)

```tjp
macro IncludeTimesheets [
  include "timesheets/2024-W03-alice.tji"
  include "timesheets/2024-W03-bob.tji"
]

${IncludeTimesheets}
```

### Subdirectory includes

```tjp
include "modules/backend/tasks.tji"
include "modules/frontend/tasks.tji"
include "modules/infrastructure/tasks.tji"
```

## Typical Project Layout

```
project/
├── project.tjp              # Main project file with project declaration
├── includes/
│   ├── accounts.tji         # Cost account definitions
│   ├── resources.tji        # Resource definitions
│   ├── tasks.tji            # Task hierarchy
│   └── reports.tji          # Report definitions
└── timesheets/
    ├── 2024-W03-alice.tji   # Weekly timesheet files
    ├── 2024-W03-bob.tji
    └── ...
```

## Include Order

The order of includes matters:

1. **Accounts** — Must be defined before tasks reference them via `chargeset`
2. **Resources** — Must be defined before tasks reference them via `allocate`
3. **Tasks** — Can reference accounts and resources
4. **Reports** — Can reference tasks and resources in filters
5. **Timesheets** — Reference existing tasks and resources

## Supplement Blocks

Include files can use `supplement` to add attributes to entities defined elsewhere:

```tjp
# In a separate include file
supplement task acme.development.backend_api {
  journalentry 2024-02-05 "Progress update" {
    author alice
    summary "API endpoints 80% complete."
  }
}

supplement resource alice {
  vacation "Sick day" 2024-02-10 - 2024-02-11
}
```

## Notes

- Include paths are relative to the file containing the `include` statement.
- The `.tjp` extension is conventionally used only for the main project file.
- All other files use `.tji` (TaskJuggler Include) extension.
- Circular includes are not allowed and will cause a compiler error.
- Include files do not need a `project` declaration — only the main `.tjp` file has one.
- The compiler processes includes in order, so forward references may cause errors.
- Use includes to keep the main project file clean and to enable team collaboration (each team member edits their own files).
