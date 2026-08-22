---
workflow_version: 1.0
phase: report
produces:
  - DATABASE_REVIEW_REPORT.md
consumes:
  - schema_findings
  - indexing_findings
  - locking_findings
  - transaction_findings
  - migration_findings
  - query_plan_findings
  - replication_findings
  - partitioning_findings
---

# Report — derive verdict, build DATABASE_REVIEW_REPORT.md

Derive the overall verdict from the eight dimensions' findings, fixed precedence, worst-first:

1. **`Rejected`** — any finding is an irreversible/destructive migration step with no rollback or backup
   path, or a blocking full-table lock on a hot/production table with no online-migration strategy.
2. **`Changes required`** — no `Rejected`-level finding, and at least one concrete correctness/safety
   defect: a missing index behind a hot query, an incorrect/unstated isolation level for a known
   concurrency need, a non-destructive migration with no rollback plan, an N+1-shaped access pattern, a
   missing constraint that risks data integrity.
3. **`Approved with conditions`** — no `Rejected`- or `Changes required`-level finding, and either only
   minor/non-blocking findings remain, or one or more dimensions were recorded `Unknown` for lack of
   evidence — an evidence gap alone is never enough to reach a bare `Approved`.
4. **`Approved`** — every dimension evaluated (no `Unknown` rows), zero findings across all eight.

Report the single highest-precedence state; list every contributing finding (not just the one that set
the verdict) across the relevant sections and in Notes.

Build per [reference/report-format.md](../reference/report-format.md).
