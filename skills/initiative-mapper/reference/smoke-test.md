# Smoke test — initiative-mapper

Run after install or any substantive edit. Use a real, large, ambiguous effort with at least 3
plausible sub-questions. The skill remains read-only: inspect repository evidence and emit a report;
do not write a ticket, PRD, plan, or any other repository state.

Conventions: [smoke-test-conventions](../../../docs/skill-framework/shared/smoke-test-conventions.md).

## Invocation

> `initiative_description: <a real large, ambiguous effort with at least 3 plausible sub-questions>`

Example: `initiative_description: Overhaul the entire auth system — replace the legacy session store,
add SSO, and support per-tenant password policies, with no agreement yet on order or ownership.`

## A correct minimal output contains

1. A HARD STOP if `initiative_description` is absent.
2. At least 3 decision tickets, each with a specific sub-question — not a restatement of the whole
   initiative.
3. Dependency edges between tickets, with a computed sequencing of what can start immediately versus
   what is blocked.
4. Each ticket's "ready for" skill stated (`engineering-decision-discovery`, `prd-architect`,
   `implementation-planner`, or explicitly `unresolved`) — never a vague "needs more thought."
5. `INITIATIVE_MAP.md` / `initiative_map` emitted as a report only — no ticket, PRD, or plan write,
   and no automatic downstream invocation.

## Degraded paths

| Condition | Expected behavior |
|-----------|---------------------|
| No `initiative_description` named | HARD STOP — ask for the effort to map |
| Description is already one bounded, scoped idea | Reject mapping; point at `prd-architect` directly rather than a one-ticket map |
| A ticket has no clear ready-for skill yet | Mark it unresolved in the report, not force-fit into one |
| Repository evidence for a ticket is unavailable | Record it as an unresolved question on that ticket, never a fabricated scope |
| Caller asks the skill to just write the tickets/PRDs directly | Reject the direct write; emit the recommendation in the report instead |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
