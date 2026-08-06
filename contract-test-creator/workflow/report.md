---
workflow_version: 1.0
phase: report
produces:
  - CONTRACT_TEST_REPORT.md
consumes:
  - test_files_written
  - verify_result
---

# Report

Render `CONTRACT_TEST_REPORT.md` at `output_dir` per
[reference/report-format.md](../reference/report-format.md).

## 1. Always produced

Even a single-target backfill or a zero-target run (§5 of
[select-targets.md](select-targets.md)) produces a report — "nothing to do, here's why" is a valid
report body, not a reason to skip writing one.

## 2. Never upgrade a status

Copy each target's tag from `verify_result` verbatim into the report table. Never round
`WRITTEN_FAILING_PROD_BUG` or `NEEDS_HUMAN` up to "done," never describe `UNVERIFIED` targets as passing,
and never describe `NEEDS_OBSERVED_INTERACTION` targets as written.

## 3. Surface production-bug findings plainly

Every `WRITTEN_FAILING_PROD_BUG` target gets its own line: the interaction, expected vs. actual, and the
suggested next skill per [SKILL.md § Cross-skill escalation](../SKILL.md#cross-skill-escalation)
(**loop-task-implementer** to fix it, or **pr-review** to flag it on the MR under review). For a
`provider`-role finding, state explicitly that the pact file was left unmodified — this skill does not
decide whether to fix the provider or the file, it hands the finding to the caller.

## 4. Role and broker context — always shown

The report header always states `Role` (`consumer`/`provider`) and `Broker` (`yes`/`no`) even on a
zero-target or fully-`UNVERIFIED` run — a reader must be able to tell which side of the contract this run
covered without reading the target list.

## 5. Close the loop

End the report with a one-line next step: "Ready to open as an MR" (all `WRITTEN_PASSING`/`UNVERIFIED`),
or "N targets need attention before merge" pointing at the `NEEDS_HUMAN` / `WRITTEN_FAILING_PROD_BUG` /
`NEEDS_OBSERVED_INTERACTION` rows.
