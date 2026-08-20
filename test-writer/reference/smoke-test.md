# Smoke test — expected minimal output

Run after install and after any edit to `SKILL.md`, `workflow/`, or `reference/`.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `request: "write unit tests for the pricing rules and integration tests for the payments DB seam"`, `repo_root: <path>`

## A correct minimal output contains

1. **No detection or generation output of its own** — test-writer never prints framework detection,
   target lists, or written test files; those remain each dispatched specialist's own output.
2. **An ordered, de-duplicated plan announced first** — `test_plan.levels` is `[unit, integration]`, with
   fixed-vocabulary `signal_source` provenance and no copied raw caller text.
3. **One dispatch per planned level** — unit-test-creator and integration-test-creator are each invoked
   once in fresh specialist contexts with ordinary caller inputs unchanged. Each child gets its own
   framework `execution_context` derived from the same parent according to runtime recursion protection;
   no unplanned specialist is invoked.
4. **Each dispatched skill's own report preserved verbatim** — the unit and integration reports appear
   under their matching `level_reports` entries without rewriting or cross-level framing.
5. **An aggregate result that accounts for both levels** — `orchestration_status` follows the documented
   status precedence, and `unfinished_levels` names every planned level whose dispatch is not `COMPLETE`
   (empty only when both specialists succeed).
6. **Portable completion semantics** — internal `COMPLETE` maps to canonical `skill_result.status: SUCCESS`;
   `PARTIAL`, `BLOCKED`, `FAILED`, and `ESCALATED` remain distinct.

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Only one of the explicitly requested unit + integration levels is invoked | Multi-level breadth was silently narrowed, possibly by a hint or old single-dispatch logic | Re-check [workflow/classify.md](../workflow/classify.md) §§1–2 and [workflow/delegate.md](../workflow/delegate.md) |
| Several specialists are invoked for an ambiguous single surface such as "test the payment flow" | Classify's "ambiguity is not breadth" ask-once gate was skipped | Re-check [workflow/classify.md](../workflow/classify.md) §3 |
| An unplanned third specialist is invoked | Delegate ignored `test_plan.levels` or reclassified during dispatch | Re-check [workflow/delegate.md](../workflow/delegate.md) §2 |
| Child dispatch copies the parent's recursion depth/visited state unchanged, or one sibling changes another sibling's context | Recursion-protection regression | Re-check [workflow/delegate.md](../workflow/delegate.md) §2 and the shared runtime contract |
| A framework/tooling detection line appears in test-writer's own output | Detection logic leaked back into this router | This router must have zero detection logic; specialist detection stays inside each `*-test-creator` |
| A specialist report looks reformatted or influences a later specialist | Regression in report isolation / fresh-context behavior | Re-check [workflow/delegate.md](../workflow/delegate.md) §§2–3 |
| Aggregate says `COMPLETE` while one level is partial, blocked, failed, escalated, or missing | Aggregate fail-closed/status precedence regressed | Re-check [workflow/aggregate.md](../workflow/aggregate.md) |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
