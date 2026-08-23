# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|--------------|----------|
| 1 | `schema`, `migration_script`, and `queries` all supplied, migration adds a nullable column + matching index, no findings | Inputs → Analyze → Report → **Approved**, all eight sections "None found" |
| 2 | Migration includes `DROP TABLE legacy_orders`, no backup/rollback path | Analyze flags a `Rejected`-level Migrations finding → **Rejected** |
| 3 | `ALTER TABLE orders ALTER COLUMN id TYPE bigint` on a hot production table, no online-migration strategy | Analyze flags a `Rejected`-level Locking finding → **Rejected** |
| 4 | A hot query in `queries` has no supporting index, nothing else wrong | Analyze flags a `Changes required`-level Indexing finding → **Changes required** |
| 5 | Only a partitioning recommendation and a column-naming nit found | Analyze flags only minor findings → **Approved with conditions** |
| 6 | `schema` and `migration_script` supplied, no `query_plan`, otherwise clean | Query plans section recorded `Unknown` → verdict floor **Approved with conditions**, never bare `Approved` |
| 7 | `schema`, `migration_script`, and `queries` all absent | Inputs HARD STOP — ask which one the caller wants reviewed, no Analyze |
| 8 | Only `queries` supplied, no `schema`/`migration_script` | Schema, Locking, Migrations, Replication sections recorded `Unknown` (nothing to evaluate); Indexing and Query plans still run |
| 9 | "Rewrite this MySQL schema for Postgres" | **Wrong skill** → mysql-to-postgres-sql directly |
| 10 | "Review merge request !410" (migration is one file among several changed) | **Wrong skill** → pr-review directly |
| 11 | "How much headroom do we have before this table needs sharding, at current growth?" | **Wrong skill** → capacity-planner directly |
| 12 | Indexing/query-plan findings point at a broader systemic slowdown across the service | Reported per [SKILL.md](SKILL.md) § Cross-skill escalation → **performance-review** |

---

### Scenario: Clean migration — happy path

**Caller:** `schema: <orders DDL>`, `migration_script: <adds nullable "notes" column + index>`,
`queries: [<order lookup by id>]`, `query_plan: <plan showing index scan>`

**Agent:**

1. Inputs — all three primary fields present plus `query_plan`; `db_engine` inferred as Postgres from
   `RETURNING`-style DDL
2. Analyze — all eight dimensions evaluated: no missing constraints, index already covers the lookup,
   `ADD COLUMN ... NULL` takes only a brief metadata lock, no destructive step, plan shows an index scan,
   no bulk backfill, table is small enough that partitioning doesn't apply
3. Report — zero findings across all eight sections, no `Unknown` rows → verdict `Approved`

**Expected fragment:**

```
# Database review — orders notes column migration

**Verdict: Approved**

## Schema

| Table/Object | Finding | Severity |
|---------------|---------|----------|
| — | None found | — |

## Indexing

| Table/Query | Finding | Severity |
|--------------|---------|----------|
| — | None found | — |

## Locking

| Statement | Finding | Severity |
|-----------|---------|----------|
| `ALTER TABLE orders ADD COLUMN notes text` | Brief metadata lock only, non-blocking at this table size | Approved |
```

---

### Scenario: Destructive migration — worst state

**Caller:** `migration_script: <DROP TABLE legacy_orders; migrates data to "orders_archive" first>`,
`schema: <legacy_orders + orders_archive DDL>`

**Agent:**

1. Inputs — `schema` and `migration_script` present, no `queries`/`query_plan`
2. Analyze — Migrations dimension flags the `DROP TABLE` as irreversible with no rollback path even though
   a prior step copies data (the drop itself has no staged-removal window or backup snapshot referenced);
   Locking flags the drop as an `ACCESS EXCLUSIVE` lock on `legacy_orders`; Query plans and Indexing
   recorded `Unknown` (no `queries`/`query_plan` supplied)
3. Report — a `Rejected`-level Migrations finding is present → verdict `Rejected` (highest precedence),
   the `Unknown` rows are listed in Notes but do not affect the verdict once `Rejected` already applies

**Expected fragment:**

```
# Database review — legacy_orders retirement migration

**Verdict: Rejected**

## Migrations

| Step | Finding | Severity |
|------|---------|----------|
| `DROP TABLE legacy_orders` | Irreversible; no backup snapshot or staged-removal window referenced before the drop | Rejected |

## Locking

| Statement | Finding | Severity |
|-----------|---------|----------|
| `DROP TABLE legacy_orders` | `ACCESS EXCLUSIVE` lock for the statement's duration | Rejected |

## Notes

Query plans and Indexing recorded `Unknown` — no `queries`/`query_plan` supplied. Verdict `Rejected` is
driven by the Migrations/Locking findings above regardless.
```

---

### Scenario: Missing index — Changes required, multi-finding

**Caller:** `schema: <orders DDL, no index on customer_id>`,
`queries: ["SELECT * FROM orders WHERE customer_id = ?"]`, `query_plan: <plan showing Seq Scan>`

**Agent:**

1. Inputs — `schema`, `queries`, `query_plan` present, no `migration_script`
2. Analyze — Indexing flags the missing `orders(customer_id)` index behind the supplied query; Query
   plans confirms a sequential scan in the supplied plan (same underlying issue, reported once per
   dimension); Locking/Migrations/Replication recorded `Unknown` (no `migration_script`)
3. Report — a `Changes required`-level Indexing finding, no `Rejected`-level finding → verdict
   `Changes required`

**Expected fragment:**

```
# Database review — orders customer lookup review

**Verdict: Changes required**

## Indexing

| Table/Query | Finding | Severity |
|--------------|---------|----------|
| `orders(customer_id)` | No index — full-table scan on the hot lookup query | Changes required |

## Query plans

| Query | Finding | Severity |
|-------|---------|----------|
| `SELECT * FROM orders WHERE customer_id = ?` | `Seq Scan` on `orders`, consistent with the missing index above | Changes required |

## Notes

Locking, Migrations, and Replication recorded `Unknown` — no `migration_script` supplied.
```

---

### Scenario: Degraded path — no query plan supplied

**Caller:** `schema: <orders DDL>`, `queries: ["SELECT * FROM orders WHERE status = ?"]` — no
`query_plan`.

**Agent:** Query plans cannot be evaluated without a captured plan — Analyze records this dimension
`Unknown` rather than guessing plan behavior from the query text, and never silently reports it as "None
found." Report's verdict-floor rule applies: an `Unknown` dimension alone, with no other findings, sets
the verdict to `Approved with conditions`, never a bare `Approved`.

**Expected fragment:**

```
## Query plans

| Query | Finding | Severity |
|-------|---------|----------|
| `SELECT * FROM orders WHERE status = ?` | `Unknown` — no `query_plan` supplied | Unknown |

## Notes

Query plans recorded `Unknown` for lack of a supplied `query_plan`. No other dimension raised a finding,
but the evidence gap keeps the verdict at `Approved with conditions` rather than `Approved`.
```

**Verdict: Approved with conditions**

---

### Scenario: Cross-skill handoff — indexing points at a systemic slowdown

**Caller:** `schema`, `queries`, and `query_plan` for three unrelated hot queries, all showing sequential
scans and missing indexes across most of the service's tables, not one isolated query.

**Agent:** Indexing and Query plans findings are reported per [reference/report-format.md](reference/report-format.md)
as usual (verdict `Changes required` at minimum), but the breadth — missing indexes across most of the
service's hot paths, not one query — matches [SKILL.md](SKILL.md) § Cross-skill escalation: "Query/index
findings suggest a broader performance problem." The report's Notes offers the handoff rather than
silently expanding this skill's own scope into a full performance audit.

**Expected fragment:**

```
## Notes

Missing indexes and sequential scans span most of the service's hot query paths, not one isolated query —
this looks like a broader performance problem beyond this schema/query set's scope. Recommend running
**performance-review** for a full service-level performance audit.
```
