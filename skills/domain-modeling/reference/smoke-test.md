# Smoke test — domain-modeling

Run after install or any substantive edit. Use a real repository with a `CONTEXT.md` (or `CONTEXT-MAP.md`)
defining at least one term, plus one session statement about that term that either matches or conflicts
with the existing definition. The skill remains read-only: inspect and emit a report; do not modify
`CONTEXT.md`, `CONTEXT-MAP.md`, `docs/adr/`, or any other fixture repository state.

Conventions: [smoke-test-conventions](../../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `domain_focus: <term or decision under discussion>` `existing_context: <CONTEXT.md/docs/adr excerpt>`
> `change_goal: <optional>`

Example: `domain_focus: Cancellation` where `CONTEXT.md` defines Cancellation as "an Order state" but the
session describes a partial-line-item cancellation the existing definition does not cover.

## A correct minimal output contains

1. A HARD STOP if `domain_focus` is absent.
2. Session evidence and existing-repository evidence labeled separately.
3. At least one terminology finding naming any conflict/gap, or explicitly stating none exists.
4. At least one edge-case scenario with the question it forces and the answer given (or "unresolved").
5. A code cross-reference row, or an explicit statement that code was not inspectable.
6. `DOMAIN_MODEL_UPDATE.md` / `domain_model_update` emitted as a report only — no `CONTEXT.md`,
   `CONTEXT-MAP.md`, or `docs/adr/*.md` write, and no automatic downstream invocation.

## Degraded paths

| Condition | Expected behavior |
|-----------|---------------------|
| No `domain_focus` named | HARD STOP — ask what term, relationship, or decision is under discussion |
| Neither `CONTEXT.md` nor `CONTEXT-MAP.md` exists | Proceed with `existing_context` empty; may propose creating `CONTEXT.md`, never create it |
| Session states a definition but no decision point exists | `adr_readiness: false`; Proposed ADR section states no decision crystallized |
| Session statement contradicts the code | Name the conflict in Code cross-reference; do not silently resolve it either way |
| Caller asks the skill to just edit `CONTEXT.md` directly | Reject the direct write; emit the proposed patch in the report instead |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
