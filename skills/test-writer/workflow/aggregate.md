---
workflow_version: 1.6
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

Aggregation is a bookkeeping gate, not a new test verdict. Every dispatched entry in `level_reports`
keeps both the complete child `skill_result` envelope and specialist report **verbatim**. Do not
summarize a specialist into a stronger or weaker status, and do not fabricate a report for a planned
child that never ran.

## Account for every planned level

Compare `test_plan.levels` to `level_reports`. Every planned level must have an explicit dispatch status
and exactly one evidence form appropriate to its lifecycle:

- a verbatim specialist `report` when the child was dispatched; or
- an explicit fixed-vocabulary `blocked_reason` when it was blocked before dispatch.

Dispatched entries must also carry `skill_result`, unchanged from the child. Pre-dispatch blocked entries
have no child `skill_result` because no child ran.

A pre-dispatch `BLOCKED` entry with neither a report nor a blocked reason is a lifecycle error. A child
that never ran must not contain a fabricated specialist report. Every `level_reports` entry must contain
exactly one of `report` or `blocked_reason`; it must not contain both. A dispatched child that returns canonical
`BLOCKED` still has a verbatim `report`; only a pre-dispatch guard rejection uses `blocked_reason`.

Derive `unfinished_levels` in the same stable order as `test_plan.levels`: include every planned level
whose `dispatch_status` is not `COMPLETE`, plus any planned level missing a valid report/status or
pre-dispatch blocked reason. A fully successful plan therefore has `unfinished_levels: []`; `PARTIAL`,
`BLOCKED`, `FAILED`, and `ESCALATED` levels remain named even though some of those outcomes are terminal.

## Overall status

Derive one internal `orchestration_status` using this precedence, highest first:

1. `FAILED` — at least one planned specialist returned canonical `FAILED`.
2. `BLOCKED` — no failure, and at least one planned level is blocked by an unresolved required input,
   HARD STOP, unavailable required capability, recursion guard, unknown level, or missing/invalid
   report/status evidence.
3. `ESCALATED` — no failure/blocker, and at least one planned specialist returned canonical `ESCALATED`.
4. `PARTIAL` — no stronger condition, and at least one planned level produced useful partial output but
   did not complete.
5. `COMPLETE` — every planned level completed its own workflow with canonical `SUCCESS` and produced its
   report.

The router **must not report COMPLETE** when any planned level is `PARTIAL`, `BLOCKED`, `FAILED`,
`ESCALATED`, missing, or still waiting on a required answer. Preserve every completed/unfinished report
or pre-dispatch blocked reason regardless of the aggregate status.

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
orchestration_status: BLOCKED
unfinished_levels: [integration]
level_reports:
  unit:
    dispatch_status: COMPLETE
    skill_result: <verbatim canonical child skill_result envelope>
    report: <verbatim UNIT_TEST_REPORT.md>
  integration:
    dispatch_status: BLOCKED
    blocked_reason: recursion_guard_rejected
```

`test_plan` is carried through unchanged from Classify; aggregation must not drop or rewrite its
fixed-vocabulary `signal_source` provenance.

When the plan contains one level because test-writer was already invoked as the entry point, this shape
still works unchanged. Normal top-level single named level requests should continue to bypass test-writer
and invoke the specialist directly.
