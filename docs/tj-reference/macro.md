# macro

Macros define reusable text fragments that can be expanded anywhere in a TaskJuggler project. They are commonly used for tooltip definitions, repeated column configurations, and shared text blocks.

## Syntax

### Definition

```tjp
macro <name> [
  <body>
]
```

- `<name>` — Macro identifier (alphanumeric + underscores).
- `<body>` — The text content to substitute when the macro is invoked. Enclosed in `[` and `]`.

### Invocation

```tjp
${<name>}
```

### With Parameters

Definition with parameters:

```tjp
macro <name> [
  <body referencing ${1}, ${2}, etc.>
]
```

Invocation with arguments:

```tjp
${<name> "arg1" "arg2"}
```

Parameters are referenced as `${1}`, `${2}`, etc. within the macro body.

## Examples

### Simple tooltip macro

```tjp
macro TaskTip [
  tooltip istask() -8<-
    '''Start: ''' <-query attribute='start'->
    '''End: ''' <-query attribute='end'->
    ----
    '''Effort: ''' <-query attribute='effort'->
    '''Duration: ''' <-query attribute='duration'->
  ->8-
]
```

### Resource tooltip macro

```tjp
macro ResourceTip [
  tooltip isresource() -8<-
    '''Resource: ''' <-query attribute='name'->
    ----
    '''Effort: ''' <-query attribute='effort'->
  ->8-
]
```

### Using macros in reports

```tjp
taskreport GanttChart "Gantt Chart" {
  columns bsi, name, start, end, effort,
         chart { ${TaskTip} scale week width 800 }
  hideresource @all
}
```

### Parameterized macro

```tjp
macro StandardReport [
  formats html
  timeformat "%Y-%m-%d"
  loadunit ${1}
  hideresource @all
]

taskreport TaskList "Task List" {
  ${StandardReport "days"}
  columns bsi, name, start, end, effort, complete
}

taskreport DetailedList "Detailed List" {
  ${StandardReport "hours"}
  columns bsi, name, start, end, effort, cost, complete
}
```

### Macro for repeated task patterns

```tjp
macro ReviewTask [
  task ${1}_review "${2} Review" {
    effort 2d
    allocate eve
    depends !${1}
  }
]

task development "Development" {
  task backend "Backend" {
    effort 10d
    allocate alice
  }
  ${ReviewTask "backend" "Backend"}

  task frontend "Frontend" {
    effort 10d
    allocate bob
  }
  ${ReviewTask "frontend" "Frontend"}
}
```

## Rich Text in Macros

Macros often contain rich text blocks using the `-8<-` ... `->8-` delimiters:

```tjp
macro ProjectHeader [
  center -8<-
    '''Project:''' <-query attribute='name'->
    '''Date:''' <-query attribute='now'->
  ->8-
]
```

### Query Syntax in Rich Text

```
<-query attribute='<attr_name>'->
```

Common query attributes:
- `name` — Entity name
- `start` — Start date
- `end` — End date
- `effort` — Planned effort
- `duration` — Duration
- `cost` — Cost
- `complete` — Completion percentage
- `now` — Current project date

## Notes

- Macros are expanded at parse time — they are pure text substitution.
- Macro definitions must appear before their first use in the file.
- Macros can reference other macros (but not recursively).
- The `[` and `]` delimiters for the macro body must be balanced.
- Macros are commonly defined at the top of report include files.
- Use macros to keep report definitions DRY (Don't Repeat Yourself).
- Parameter numbering starts at `${1}` (not `${0}`).
- Macros do not create a new scope — they expand inline.
