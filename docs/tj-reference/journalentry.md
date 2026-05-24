# journalentry

The `journalentry` keyword records status updates, decisions, notes, or progress information against a task or at the project level. Journal entries appear in status reports and journal reports.

## Syntax

```tjp
journalentry <date> "<headline>" {
  author <resource_id>
  [summary "<text>"]
  [alert <level>]
  [flags <flag_list>]
}
```

- `<date>` — Entry date in `YYYY-MM-DD` format.
- `<headline>` — Short description (at most 120 characters, quoted string).

## Attributes

| Attribute | Description | Example |
|-----------|-------------|---------|
| `author` | Resource ID of the entry author | `author eve` |
| `summary` | Detailed description (rich text, multi-line) | `summary "Detailed notes..."` |
| `alert` | Alert level for status reports | `alert green`, `alert yellow`, `alert red` |
| `flags` | Custom flags for filtering | `flags weekly_update` |
| `details` | Extended details (rich text) | `details -8<- ... ->8-` |

## Alert Levels

| Level | Meaning |
|-------|---------|
| `green` | Normal, on track |
| `yellow` | Warning, minor issues |
| `red` | Critical, needs immediate attention |

## Placement

Journal entries are placed inside a `task` block:

```tjp
task backend_api "Backend API" {
  effort 15d
  allocate alice

  journalentry 2024-02-01 "API design review completed" {
    author eve
    summary "Reviewed REST API design with team. Approved schema with minor changes to auth endpoints."
  }
}
```

Or they can be added to a supplement block for existing tasks:

```tjp
supplement task acme.development.backend_api {
  journalentry 2024-02-05 "Sprint progress update" {
    author alice
    alert green
    summary "All endpoints on track. Auth module 80% complete."
  }
}
```

## Examples

### Simple journal entry

```tjp
journalentry 2024-02-01 "Project kickoff completed" {
  author eve
}
```

### Journal entry with summary

```tjp
journalentry 2024-02-05 "Architecture decision: microservices" {
  author alice
  summary "Decided to use microservices architecture for the backend. Key reasons: independent deployment, team autonomy, and technology flexibility."
}
```

### Journal entry with alert

```tjp
journalentry 2024-02-12 "Dependency delay risk" {
  author eve
  alert yellow
  summary "Third-party API integration delayed by 1 week. May impact frontend integration timeline."
}
```

### Critical alert entry

```tjp
journalentry 2024-03-01 "Production incident" {
  author alice
  alert red
  summary "Database migration failed in staging. Rolling back and investigating. Deployment blocked until resolved."
}
```

### Multi-line summary using rich text

```tjp
journalentry 2024-02-15 "Sprint retrospective" {
  author eve
  summary -8<-
    '''What went well:'''
    * Completed all planned stories
    * Good collaboration between frontend and backend teams

    '''What to improve:'''
    * Need better test coverage before merging
    * Stand-ups running too long
  ->8-
}
```

## Journal Reports

Journal entries are displayed using `taskreport` with journal mode:

```tjp
taskreport JournalReport "Project Journal" {
  formats html
  headline "Project Journal"
  columns name, journal
  journalmode journal
  journalattributes headline, author, date, summary
}
```

### Journal Modes

| Mode | Description |
|------|-------------|
| `journal` | Show all journal entries |
| `status_up` | Show status entries, rolling up from leaves |
| `status_down` | Show status entries, rolling down from root |
| `alerts_up` | Show only alert entries, rolling up |
| `alerts_down` | Show only alert entries, rolling down |

### Journal Attributes

| Attribute | Description |
|-----------|-------------|
| `headline` | Show the headline text |
| `author` | Show the author resource |
| `date` | Show the entry date |
| `summary` | Show the summary text |
| `details` | Show the details text |
| `alert` | Show the alert level |
| `flags` | Show the flags |

## Notes

- Journal entries are the primary mechanism for recording project status and decisions.
- The `headline` should be concise (max 120 characters) — use `summary` for details.
- Journal entries with `alert` levels appear in status reports and can trigger notifications.
- Entries are sorted by date (newest first) in journal reports.
- The `author` must reference a valid resource ID defined in the project.
- Journal entries can be added to any task at any level of the hierarchy.
- Use `supplement task` blocks to add journal entries to tasks defined in other files.
