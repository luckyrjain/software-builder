# Smoke test — expected minimal output

Run after install or any edit to this skill. Use an approved architecture decision (or a PRD with a
build-ready section) with enough detail to derive components, an API/event surface, and a data model, plus
a second, sparser input that omits load/capacity data to exercise the "Ready with open questions" path,
not just the clean path.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `architecture_decision_or_prd: <architecture decision or PRD text>` `existing_system_context: <optional>`

Example: `architecture_decision_or_prd: "Architecture Decision: Order Service — Approved. Owns order
lifecycle, publishes order.created/order.paid events, backed by Postgres..."`

## A correct minimal output contains

1. **Phase announcement** — Inputs parsed and confirmed before Analyze starts.
2. **Scope announcement** — which architecture decision/PRD is being designed against, and whether
   existing-system context was supplied.
3. **Core findings table or explicit "none"** for each of Components, APIs, Events, Data model, State
   machines, Consistency, Retries & idempotency, Capacity, Failure strategy, Observability, and Rollout
   plan — every section present, never silently dropped.
4. **`SYSTEM_DESIGN_SPEC.md` produced**, per [reference/report-format.md](report-format.md), with a
   bold Readiness verdict line and every section populated or explicitly marked "Open question."
5. **Confirmation / next-step** — a pointer to the relevant cross-skill escalation row when a section's
   finding warrants one (e.g. API surface defined → api-design-review).

## Degraded paths

| Condition | Expected behavior |
|-----------|----------------------|
| No architecture decision or PRD text supplied | Inputs HARD STOP — ask for it, per [workflow/inputs.md](../workflow/inputs.md); Analyze never starts |
| Input has no load/traffic data | Capacity section recorded as an explicit "Open question," verdict capped at "Ready with open questions," never fabricated into a number |
| No existing-system context supplied | Rollout/migration-order section notes the gap explicitly where it matters (e.g. no known current state to migrate from); does not block Components/APIs/data model analysis |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
