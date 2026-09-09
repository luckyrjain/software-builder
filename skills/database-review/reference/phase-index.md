# Phase index

**One `workflow/` file per phase** — never bulk-load workflow or reference files. Each file declares
`workflow_version`, `phase`, `produces`, and `consumes`.

| Step | Read now | Produces |
|------|----------|----------|
| **Inputs** | [workflow/inputs.md](../workflow/inputs.md) | `schema`, `migration_script`, `queries`, `query_plan`, `db_engine` |
| **Analyze** | [workflow/analyze.md](../workflow/analyze.md) | per-dimension findings (schema, indexing, locking, transactions, migrations, query plans, replication, partitioning) |
| **Report** | [workflow/report.md](../workflow/report.md) | `DATABASE_REVIEW_REPORT.md` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller sends | Phases |
|---------------|--------|
| A DDL schema, a migration script, and representative queries | Inputs → Analyze → Report → full verdict |
| `schema`, `migration_script`, and `queries` all absent | Inputs HARD STOP — ask, no Analyze |
| A migration script with no `query_plan` supplied | Analyze records the query-plan-dependent checks as `Unknown` → Report surfaces it as an explicit gap, not a silent pass |
