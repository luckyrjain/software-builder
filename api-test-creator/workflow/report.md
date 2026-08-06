---
workflow_version: 1.0
phase: report
produces:
  - API_TEST_REPORT.md
  - API_TEST_COVERAGE_STATE.yaml
consumes:
  - test_files_written
  - verify_result
---

# Report

Render `API_TEST_REPORT.md` at `output_dir` per
[reference/report-format.md](../reference/report-format.md).

## 1. Always produced

Even a single-target backfill or a zero-target run (§7 of
[select-targets.md](select-targets.md)) produces a report — "nothing to do, here's why" is a valid report
body, not a reason to skip writing one.

## 2. Never upgrade a status

Copy each target's tag from `verify_result` verbatim into the report table. Never round
`WRITTEN_FAILING_PROD_BUG` or `NEEDS_HUMAN` up to "done," never describe `UNVERIFIED` or `NEEDS_API_ENV`
targets as passing, and never describe `NEEDS_OBSERVED_ENDPOINT` targets as written.

## 3. Surface production-bug findings plainly

Every `WRITTEN_FAILING_PROD_BUG` target gets its own line: the endpoint, expected vs. actual (status code,
schema/field, or header), and the suggested next skill per
[SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation) (**loop-task-implementer** to fix
it, or **pr-review** to flag it on the MR under review).

## 4. Collection context — always shown

The report header always states the resolved `Collection` path and `Newman` availability (`yes`/`no`) even
on a zero-target or fully-`UNVERIFIED`/`NEEDS_API_ENV` run — a reader must be able to tell which collection
this run extended without reading the target list.

## 5. Write incremental backfill state (optional, backfill mode only)

For a backfill run, upsert `API_TEST_COVERAGE_STATE.yaml` at `output_dir` per
[test-creation-principles.md §6](../../docs/skill-framework/shared/test-creation-principles.md#6-incremental-backfill-state-optional):
one entry per target this run actually attempted, and every newly `SKIPPED_MAX_FILES` target added to
`pending_backlog`. Skip this step for a diff-mode run. Never let a write failure here block the report
from being produced.

## 6. Close the loop

End the report with a one-line next step: "Ready to open as an MR" (all
`WRITTEN_PASSING`/`UNVERIFIED`), "N targets need attention before merge" pointing at the `NEEDS_HUMAN` /
`WRITTEN_FAILING_PROD_BUG` / `NEEDS_OBSERVED_ENDPOINT` rows, "N targets blocked — supply a reachable API
instance" when `NEEDS_API_ENV` accounts for the remainder, or — when `pending_backlog` is non-empty —
"N targets remain; re-run to continue."
