---
workflow_version: 1.1
phase: aggregate
produces:
  - orchestration_status
  - level_reports
consumes:
  - test_plan
  - level_reports
---

# Aggregate — report orchestration state without rewriting specialist evidence

Aggregation is a bookkeeping gate, not a new test verdict. Every entry in `level_reports` keeps the
specialist's report **verbatim**. Do not summarize a specialist into a stronger or weaker status.

## Account for every planned level

Compare `test_plan.levels` to `level_reports`. Every planned level must have an explicit dispatch status
and its raw report or an explicit blocked reason. An unaccounted planned level is a lifecycle error.

## Overall status

- `COMPLETE` — every planned level completed its own workflow and produced its report.
- `PARTIAL` — at least one planned level produced useful partial output but did not complete, while no
  stronger blocking condition requires `BLOCKED`.
- `BLOCKED` — a planned level cannot proceed because of an unresolved required input, HARD STOP,
  unavailable required capability, unknown level, or missing report/status.

The router **must not report COMPLETE** when any planned level is `PARTIAL`, `BLOCKED`, missing, or still
waiting on a required answer.

## Portable `skill_result` mapping

`orchestration_status` is internal bookkeeping and does not extend the universal status vocabulary.
When emitting the canonical result envelope from
[runtime-contract.md](../../docs/skill-framework/shared/runtime-contract.md):

| `orchestration_status` | `skill_result.status` |
|------------------------|-----------------------|
| `COMPLETE` | `SUCCESS` |
| `PARTIAL` | `PARTIAL` |
| `BLOCKED` | `BLOCKED` |

Never emit `COMPLETE` as `skill_result.status`; it is not a portable runtime status. If execution itself
fails before a valid aggregate can be produced, use the inherited runtime contract's `FAILED` semantics
rather than inventing another orchestration state.

## Output shape

```yaml
test_plan:
  levels: [unit, integration]
orchestration_status: COMPLETE | PARTIAL | BLOCKED
unfinished_levels: []
level_reports:
  unit:
    dispatch_status: COMPLETE
    report: <verbatim UNIT_TEST_REPORT.md>
  integration:
    dispatch_status: COMPLETE
    report: <verbatim INTEGRATION_TEST_REPORT.md>
```

When the plan contains one level because test-writer was already invoked as the entry point, this shape
still works unchanged. Normal top-level single named level requests should continue to bypass test-writer
and invoke the specialist directly.
