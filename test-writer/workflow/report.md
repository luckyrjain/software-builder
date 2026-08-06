---
workflow_version: 1.0
phase: report
produces:
  - TEST_WRITER_REPORT.md
consumes:
  - test_files_written
  - verify_result
---

# Report

Render `TEST_WRITER_REPORT.md` at `output_dir` per [reference/report-format.md](../reference/report-format.md).

## 1. Always produced

Even a single-target backfill or a zero-target run (§5 of
[select-targets.md](select-targets.md)) produces a report — "nothing to do, here's why" is a valid
report body, not a reason to skip writing one.

## 2. Never upgrade a status

Copy each target's tag from `verify_result` verbatim into the report table. Never round
`WRITTEN_FAILING_PROD_BUG` or `NEEDS_HUMAN` up to "done," and never describe `UNVERIFIED` targets as
passing.

## 3. Surface production-bug findings plainly

Every `WRITTEN_FAILING_PROD_BUG` target gets its own line: the assertion, expected vs. actual, and the
suggested next skill per [SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation)
(**loop-task-implementer** to fix it, or **pr-review** to flag it on the MR under review). This skill
does not decide which — it hands the finding to the caller.

## 4. Coverage delta — best-effort only

If `coverage_tool_hint` was set, or a coverage tool was detected as part of the framework's own tooling
(e.g. `coverage.py`, `nyc`, `go test -cover`) and ran cleanly alongside verification, include a before/
after coverage delta for the touched files. Omit the section entirely (not a "0%" placeholder) when no
coverage tool ran — this is enrichment, not a required output.

## 5. Close the loop

End the report with a one-line next step: "Ready to open as an MR" (all `WRITTEN_PASSING`/`UNVERIFIED`),
or "N targets need attention before merge" pointing at the `NEEDS_HUMAN` /
`WRITTEN_FAILING_PROD_BUG` rows.
