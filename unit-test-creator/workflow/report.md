---
workflow_version: 1.0
phase: report
produces:
  - UNIT_TEST_REPORT.md
consumes:
  - test_files_written
  - verify_result
---

# Report

Render `UNIT_TEST_REPORT.md` at `output_dir` per
[reference/report-format.md](../reference/report-format.md), which follows the shared skeleton in
[test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton).

## 1. Always produced

Even a single-target backfill or a zero-target run (§5 of
[select-targets.md](select-targets.md)) produces a report — "nothing to do, here's why" is a valid
report body, not a reason to skip writing one.

## 2. Never upgrade a status

Copy each target's tag from `verify_result` verbatim into the report table. Never round
`WRITTEN_FAILING_PROD_BUG`, `UNTESTABLE_WITHOUT_FIXTURE`, or `NEEDS_HUMAN` up to "done," and never
describe `UNVERIFIED` targets as passing.

## 3. Surface production-bug findings plainly

Every `WRITTEN_FAILING_PROD_BUG` target gets its own line: the assertion, expected vs. actual, and the
suggested next skill per
[SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation) (**loop-task-implementer** to fix
it, or **pr-review** to flag it on the MR under review). This skill does not decide which — it hands the
finding to the caller.

## 4. Surface isolation findings plainly

Every `UNTESTABLE_WITHOUT_FIXTURE` target also gets its own `## Findings` line: the reason it can't be
isolated, and a pointer to **integration-test-creator** as the skill that can write a real test against
the real dependency. This is a normal, expected outcome for some targets, not a failure of this run.

## 5. Close the loop

End the report with a one-line next step: "Ready to open as an MR" (all `WRITTEN_PASSING`/`UNVERIFIED`),
or "N targets need attention before merge" pointing at the `NEEDS_HUMAN` / `WRITTEN_FAILING_PROD_BUG` /
`UNTESTABLE_WITHOUT_FIXTURE` rows.
