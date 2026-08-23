---
workflow_version: 1.0
phase: analyze
produces:
  - schema_findings
  - indexing_findings
  - locking_findings
  - transaction_findings
  - migration_findings
  - query_plan_findings
  - replication_findings
  - partitioning_findings
consumes:
  - schema
  - migration_script
  - queries
  - query_plan
  - db_engine
---

# Analyze — evaluate the supplied schema, migration, and/or queries across eight dimensions

Run every dimension below against whatever inputs were supplied. A dimension with nothing to evaluate
(e.g. Locking when only `queries` were supplied, no `schema`/`migration_script`) is recorded `Unknown`,
not silently skipped — see § Evidence gaps below.

## 1. Schema

Review `schema` DDL for design defects: missing `NOT NULL`/`CHECK`/`UNIQUE` constraints implied by the
domain, ambiguous or inconsistent typing (e.g. a monetary column as `float`), missing foreign keys where a
relationship is implied, denormalization that isn't justified by an access pattern shown in `queries`.

## 2. Indexing

Cross-reference whichever of `schema`'s existing indexes and `migration_script`'s DDL changes are
supplied against `queries`: missing indexes behind a hot `WHERE`/`JOIN`/`ORDER BY` clause, redundant
indexes (one is a strict prefix of another), wrong column order in a composite index relative to the
query's filter/sort pattern, indexes added that no supplied query actually uses. `queries` is the only
input this dimension strictly needs — with only `queries` supplied (no `schema`/`migration_script`),
still flag hot clauses with no evident supporting index in whatever DDL is available; the
redundant-index, column-order, and unused-added-index checks simply don't apply rather than being a
separate evidence gap.

## 3. Locking

For each DDL statement in `schema`/`migration_script`, determine the lock class it takes under the
resolved (or asked) `db_engine` — e.g. Postgres `ACCESS EXCLUSIVE` on most `ALTER TABLE` forms, MySQL's
metadata-lock/online-DDL distinction — and whether it blocks reads, writes, or both, and for how long
relative to table size. Flag any blocking lock on what appears to be a hot/production table with no
online-migration strategy (e.g. `pt-online-schema-change`, Postgres's `CREATE INDEX CONCURRENTLY`,
expand-contract).

## 4. Transactions

Check transaction boundaries implied by `migration_script`/`queries`: multi-statement changes that should
be atomic but aren't wrapped in a transaction, an isolation level that's unstated or mismatched to a known
concurrency need (e.g. read-then-write without `SELECT ... FOR UPDATE` under a concurrency-sensitive
path), a migration that mixes DDL and DML in one transaction against an engine where that's unsafe.

## 5. Migrations

Assess `migration_script` for safety: reversibility (is there a corresponding down-migration or rollback
plan), destructive operations (`DROP COLUMN`/`DROP TABLE`/`TRUNCATE`) without a backup or staged-removal
path, whether it's safe to run online against a live, populated table, and whether a large backfill is
batched rather than a single unbounded statement.

## 6. Query plans

When `query_plan` is supplied, check for sequential scans on large tables where an index should apply,
N+1-shaped access patterns across `queries` (a loop-shaped repeated single-row lookup instead of a batch
query), and missing `LIMIT`/pagination on an unbounded result set. **When `query_plan` is absent, record
this dimension `Unknown` per query** — do not infer plan behavior from the query text alone and report it
as a finding.

## 7. Replication

Assess replication impact of `migration_script`/`queries`: large single-statement backfills or bulk
deletes that risk replica lag, DDL forms that replicate poorly under the resolved `db_engine` (e.g.
statement-based replication hazards), and any change that could desync a read replica used for
query-serving.

## 8. Partitioning

For large or fast-growing tables in `schema` (especially append-only, time-ordered, or explicitly
high-volume tables), assess whether a partitioning strategy is present, appropriate, and matches the
access pattern in `queries` (e.g. partition key aligned with the most common filter column).

## Evidence gaps

Any dimension above that cannot be evaluated for lack of the relevant input (no `schema`/
`migration_script` for Locking/Migrations/Replication, no `queries` for Indexing's usage cross-check, no
`query_plan` for Query plans) is recorded as an explicit `Unknown` finding for that dimension — never
silently dropped, never folded into "no finding." This gap record feeds Report's verdict-floor rule for
`Unknown` rows.
