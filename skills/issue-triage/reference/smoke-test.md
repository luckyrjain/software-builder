# Smoke test — issue-triage

Run after install or any substantive edit. Use a small fixture batch of raw issues, at least one of
which plausibly duplicates another. The skill remains read-only: inspect and emit a report; do not
write a label, state transition, or tracker field, or any other fixture repository state.

Conventions: [smoke-test-conventions](../../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `issues: ["Checkout submit throws NullPointerException in CheckoutService.submit when the cart has a
> removed item.", "Add CSV export for order history so support can pull records without DB access.",
> "Checkout crashes on submit with a null pointer in CheckoutService.submit — same stack trace as the
> other checkout crash report."]`

Example: the first and third issues share the exact stack trace (`NullPointerException at
CheckoutService.submit`); the second is an unrelated feature request.

## A correct minimal output contains

1. A HARD STOP if `issues` is absent.
2. Category and severity for every issue, each citing the text that supports it.
3. A `duplicate_of` finding for the first/third pair citing the matching stack trace — not a guess
   from proximity or shared topic.
4. A recommended owner cited from CODEOWNERS/squad-map/prior-handling evidence, or "unclear — no
   ownership evidence found" when no such evidence exists.
5. `ISSUE_TRIAGE_REPORT.md` / `issue_triage_report` emitted as a report only — no label, state, or
   tracker field written, and no automatic downstream invocation.

## Degraded paths

| Condition | Expected behavior |
|-----------|---------------------|
| No `issues` supplied | HARD STOP — ask for the raw issue text(s) |
| An issue is a bare title with no description | Recorded as "insufficient detail to classify," not skipped |
| Two issues are filed close together but share no symptom/stack-trace/repro evidence | `duplicate_of: none found` for both |
| An issue describes active, ongoing user-facing impact right now | Named under "Incident-shaped issues"; `incident-rca` offered |
| Caller asks the skill to just apply the labels | Reject the direct write; emit the classification in the report instead |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
