# database-review

Reviews a database **schema, migration script, and/or a set of representative queries** across eight
dimensions — schema design, indexing, locking, transactions, migration safety, query plans, replication
impact, and partitioning — and produces a verdicted `DATABASE_REVIEW_REPORT.md`. No MCP dependency: it
works from supplied DDL/migration/query text and repository content only.

## When to use

- Reviewing a proposed schema or DDL change for design defects (missing constraints, ambiguous typing).
- Reviewing a migration script for locking behavior, transaction safety, and rollback/online-migration
  strategy before it ships.
- Reviewing a set of representative queries for missing/redundant indexes or N+1-shaped access, with or
  without a captured query plan.
- Checking replication impact of a large backfill/bulk change, or whether a large table needs a
  partitioning strategy.

Not for a MySQL→Postgres dialect rewrite (use **mysql-to-postgres-sql**), a full MR review of which a
migration is one part (use **pr-review**), or capacity/growth forecasting (use **capacity-planner**).

## Install

```bash
cd software-builder
make install-database-review
```

Full setup, prerequisites, and troubleshooting: [SETUP.md](SETUP.md).

## Pipeline

`Inputs → Analyze → Report`

Agent instructions: [SKILL.md](SKILL.md).
