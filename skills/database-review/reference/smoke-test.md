# Smoke test — expected minimal output

Run after install or any edit to this skill. Use a small representative migration script (e.g. one that
adds a nullable column plus an index) alongside its schema DDL and 1-2 representative queries so all eight
analysis dimensions have something to evaluate, not just the trivial "no findings" path.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `schema: <DDL text>`, `migration_script: <migration file content>`, `queries: [<representative query>, ...]`

## A correct minimal output contains

1. **Scope announcement** — which of `schema`/`migration_script`/`queries`/`query_plan` were supplied,
   and `db_engine` (inferred or asked).
2. **Findings table or explicit "None found" for each of the eight sections** — Schema, Indexing,
   Locking, Transactions, Migrations, Query plans, Replication, Partitioning — none silently omitted.
3. **`DATABASE_REVIEW_REPORT.md`** built per [report-format.md](report-format.md), with a bold verdict
   line using one of the four enum values.
4. **Confirmation of next step** — pointing at [reference/report-format.md](report-format.md) for the full
   structure and, when applicable, a cross-skill escalation line per [SKILL.md](../SKILL.md) § Cross-skill
   escalation.

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| No `query_plan` supplied | Query plans section records `Unknown` per query, not a silent "no finding"; verdict floor is `Approved with conditions` even if nothing else is found |
| Only `queries` supplied, no `schema`/`migration_script` | Schema, Locking, Migrations, and Replication sections record `Unknown` (nothing to evaluate for those dimensions); Indexing and Query plans still run against the supplied queries |
| `schema`, `migration_script`, and `queries` all absent | Inputs HARD STOP — ask which one the caller wants reviewed, no Analyze phase runs |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
