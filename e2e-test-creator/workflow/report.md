---
workflow_version: 1.0
phase: report
produces:
  - E2E_TEST_REPORT.md
  - E2E_TEST_COVERAGE_STATE.yaml
consumes:
  - test_files_written
  - verify_result
---

# Render the deliverable report

Render `E2E_TEST_REPORT.md` at `output_dir` per
[reference/report-format.md](../reference/report-format.md), which follows the shared skeleton in
[test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton).

## 1. Always produced

Even a single-journey backfill or a zero-journey diff run (§7 of
[select-targets.md](select-targets.md)) produces this deliverable — "nothing to do, here's why" is a
valid body, not a reason to skip writing one.

## 2. Never upgrade a status

Copy each journey's tag from `verify_result` verbatim into the deliverable table. Never round
`WRITTEN_FAILING_PROD_BUG` or `NEEDS_HUMAN` up to "done," never describe `UNVERIFIED` journeys as passing,
and never describe a `NEEDS_BROWSER_ENV` journey as anything other than blocked.

## 3. Surface production-bug findings plainly

Every `WRITTEN_FAILING_PROD_BUG` journey gets its own line: the assertion, expected vs. actual, and the
suggested next skill per [SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation)
(**loop-task-implementer** to fix it, or **pr-review** to flag it on the MR under review). This skill does
not decide which — it hands the finding to the caller.

## 4. NEEDS_BROWSER_ENV — say what's missing, don't fabricate

When one or more journeys are blocked because no reachable app instance existed this session, the
deliverable states exactly that — never a guess at what the UI would have shown had it run. Name what
would resolve it (a local start command, a staging URL, or a preview deployment) as the next step for
those journeys.

## 5. Write incremental backfill state (optional, backfill mode only)

For a backfill run, upsert `E2E_TEST_COVERAGE_STATE.yaml` at `output_dir` per
[test-creation-principles.md §6](../../docs/skill-framework/shared/test-creation-principles.md#6-incremental-backfill-state-optional):
one entry per journey this run actually attempted, and every newly `SKIPPED_MAX_FILES` journey added to
`pending_backlog`. Skip this step for a diff-mode run. Never let a write failure here block the
deliverable from being produced.

## 6. Close the loop

End the deliverable with a one-line next step: "Ready to open as an MR" (all `WRITTEN_PASSING`/
`UNVERIFIED`), "N journeys need attention before merge" pointing at the `NEEDS_HUMAN` /
`WRITTEN_FAILING_PROD_BUG` rows, "N journeys blocked — supply a reachable app instance" for
`NEEDS_BROWSER_ENV`, or — when `pending_backlog` is non-empty — "N journeys remain; re-run to continue."
