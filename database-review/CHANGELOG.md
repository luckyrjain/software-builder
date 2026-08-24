# Changelog — database-review

## 1.1.0

- Add v2 machine summary output and typed `assessment_context` embedded input handling.

## 1.0.0 — 2026-08-22

### Added

- Initial release: reviews a supplied database schema/DDL, migration script, and/or representative
  queries across eight dimensions (schema, indexing, locking, transactions, migrations, query plans,
  replication, partitioning) and produces a verdicted `DATABASE_REVIEW_REPORT.md` via the
  Inputs → Analyze → Report pipeline.
