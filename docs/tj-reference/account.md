# account

The `account` keyword defines cost accounts for tracking project expenditures and revenue. Accounts can be nested to form a hierarchical cost breakdown structure. Tasks reference accounts via `chargeset` to assign their costs.

## Syntax

```tjp
account <id> "<name>" {
  [attributes...]
  [nested accounts...]
}
```

- `<id>` — Unique identifier (alphanumeric + underscores).
- `<name>` — Human-readable account name (quoted string).

## Attributes

| Attribute | Description | Example |
|-----------|-------------|---------|
| `account` | Nested sub-account | `account backend "Backend Development"` |
| `credit` | Add a credit (income) entry | `credit 2024-01-15 "Contract payment" 50000` |
| `flags` | Custom flags for filtering | `flags overhead` |
| `aggregate` | Aggregation method for sub-accounts | `aggregate resources` |

## Examples

### Simple cost hierarchy

```tjp
account cost "Project Costs" {
  account dev "Development" {
    account backend "Backend Development"
    account frontend "Frontend Development"
  }
  account design "Design"
  account qa "Quality Assurance"
  account mgmt "Project Management"
}
```

### Revenue accounts

```tjp
account revenue "Revenue" {
  account contract "Contract Payment"
  account maintenance "Maintenance Fees"
}
```

### Account with credits

```tjp
account revenue "Revenue" {
  credit 2024-01-15 "Initial payment" 100000
  credit 2024-04-01 "Milestone payment" 75000
  credit 2024-07-01 "Final payment" 50000
}
```

### Using accounts with tasks

```tjp
task backend_api "Backend API" {
  effort 15d
  allocate alice
  chargeset backend
}
```

## Account Reports

Accounts are displayed using `accountreport`:

```tjp
accountreport CostReport "Cost Report" {
  formats html
  headline "Financial Summary"
  columns no, name, cost, weekly
}
```

## Notes

- Accounts must be defined before they are referenced by `chargeset` in tasks.
- Leaf accounts accumulate costs from tasks that reference them via `chargeset`.
- Container accounts aggregate costs from their children.
- The `cost` column in reports shows the accumulated cost for each account.
- Use separate top-level accounts for costs and revenue to enable profit/loss analysis.
- Account IDs used in `chargeset` refer to the leaf account ID directly (not the full path).
