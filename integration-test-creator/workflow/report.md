---
workflow_version: 1.0
phase: report
produces:
  - INTEGRATION_TEST_REPORT.md
consumes:
  - test_files_written
  - verify_result
---

# Report

Render `INTEGRATION_TEST_REPORT.md` at `output_dir` per
[reference/report-format.md](../reference/report-format.md), which follows the shared skeleton in
[test-creation-principles.md §4](../../docs/skill-framework/shared/test-creation-principles.md#4-reporting-format-shared-skeleton).

## 1. Always produced

Even a single-target backfill or a zero-target run (§5 of
[select-targets.md](select-targets.md)) produces a report — "nothing to do, here's why" is a valid
report body, not a reason to skip writing one.

## 2. Never upgrade a status

Copy each target's tag from `verify_result` verbatim into the report table. Never round
`WRITTEN_FAILING_PROD_BUG`, `NEEDS_HUMAN`, or `NEEDS_INTEGRATION_ENV` up to "done," and never describe
`UNVERIFIED`/`NEEDS_INTEGRATION_ENV` targets as passing.

## 3. Surface production-bug findings plainly

Every `WRITTEN_FAILING_PROD_BUG` target gets its own line: the assertion, expected vs. actual, and the
suggested next skill per
[SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation) (**loop-task-implementer** to
fix it, or **pr-review** to flag it on the MR under review). This skill does not decide which — it hands
the finding to the caller.

## 4. Surface `NEEDS_INTEGRATION_ENV` plainly, not as a soft failure

Every `NEEDS_INTEGRATION_ENV` target gets a line naming exactly what's missing (no testcontainers
dependency, no docker-compose file, no reachable Docker daemon) and what would unblock it — never folded
silently into a generic "needs human" bucket, since the fix here is infrastructure, not a decision.

## 5. Close the loop

End the report with a one-line next step: "Ready to open as an MR" (all `WRITTEN_PASSING`/`UNVERIFIED`),
or "N targets need attention before merge" pointing at the `NEEDS_HUMAN` / `WRITTEN_FAILING_PROD_BUG` /
`NEEDS_INTEGRATION_ENV` rows.
