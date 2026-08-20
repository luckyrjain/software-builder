---
workflow_version: 1.3
phase: aggregate
produces:
  - orchestration_status
  - unfinished_levels
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

Derive `unfinished_levels` in the same stable order as `test_plan.levels`: include every planned level
whose `dispatch_status` is not `COMPLETE`, plus any planned level missing a report/status. A fully
successful plan therefore has `unfinished_levels: []`; `PARTIAL`, `BLOCKED`, `FAILED`, and `ESCALATED`
levels remain named even though some of those outcomes are terminal.

## Overall status

Derive one internal `orchestration_status` using this precedence, highest first:

1. `FAILED` — at least one planned specialist returned canonical `FAILED`.
2. `BLOCKED` — no failure, and at least one planned level is blocked by an unresolved required input,
   HARD STOP, unavailable required capability, unknown level, or missing report/status.
3. `ESCALATED` — no failure/blocker, and at least one planned specialist returned canonical `ESCALATED`.
4. `PARTIAL` — no stronger condition, and at least one planned level produced useful partial output but
   did not complete.
5. `COMPLETE` — every planned level completed its own workflow with canonical `SUCCESS` and produced its
   report.

The router **must not report COMPLETE** when any planned level is `PARTIAL`, `BLOCKED`, `FAILED`,
`ESCALATED`, missing, or still waiting on a required answer. Preserve every completed/unfinished report
regardless of the aggregate status.

## Portable `skill_result` mapping

`orchestration_status` is internal bookkeeping and does not extend the universal status vocabulary.
When emitting the canonical result envelope from
[runtime-contract.md](../../docs/skill-framework/shared/runtime-contract.md):

| `orchestration_status` | `skill_result.status` |
|------------------------|-----------------------|
| `COMPLETE` | `SUCCESS` |
| `PARTIAL` | `PARTIAL` |
| `BLOCKED` | `BLOCKED` |
| `FAILED` | `FAILED` |
| `ESCALATED` | `ESCALATED` |

Never emit `COMPLETE` as `skill_result.status`; it is not a portable runtime status. `FAILED` and
`ESCALATED` are propagated rather than collapsed into another state, so the aggregate never hides a
specialist's authoritative outcome.

## Output shape

```yaml
test_plan:
  levels: [unit, integration]
  signal_source:
    unit: explicit_request
    integration: explicit_request
orchestration_status: COMPLETE | PARTIAL | BLOCKED | FAILED | ESCALATED
unfinished_levels: []
level_reports:
  unit:
    dispatch_status: COMPLETE | PARTIAL | BLOCKED | FAILED | ESCALATED
    report: <verbatim UNIT_TEST_REPORT.md>
  integration:
    dispatch_status: COMPLETE | PARTIAL | BLOCKED | FAILED | ESCALATED
    report: <verbatim INTEGRATION_TEST_REPORT.md>
```

`test_plan` is carried through unchanged from Classify; aggregation must not drop or rewrite its
fixed-vocabulary `signal_source` provenance.

When the plan contains one level because test-writer was already invoked as the entry point, this shape
still works unchanged. Normal top-level single named level requests should continue to bypass test-writer
and invoke the specialist directly.
