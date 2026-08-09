# Smoke test — expected minimal output

Run after install and after any edit to `SKILL.md`, `workflow/`, `reference/`, or `report-template.md`.

Conventions: [smoke-test-conventions](../../docs/skill-framework/shared/smoke-test-conventions.md)

## Invocation

> `request: "Add an admin control that lets support temporarily disable new user registrations."`

## A correct minimal output contains

1. **Depth header** — `Depth: Lite — …` with a one-line reason.
2. **Single coherent PRD** — no separate draft and no "reviewer comments" the reader must reconcile.
3. **Triggered sections only** — Overview, Problem, Goals/Non-Goals, MVP, functional requirements,
   key failure/edge cases, acceptance criteria, risks; no empty N/A blocks.
4. **Product behavior, not implementation prescription** — admin authorization, enable/disable behavior,
   audit log, user-facing registration state; no database or framework choices unless constrained.
5. **Build Readiness verdict** — exactly one of Ready / Ready With Non-Blocking Questions / Not Ready
   with rationale tied to gates.
6. **No external mutations** — no tickets created, repos modified, or messages sent unless explicitly
   requested separately.

## Failure diagnosis

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Two documents (draft + repaired) | Repair output leaked | One final artifact per [output-contract.md](output-contract.md) |
| Generic security boilerplate | Break phase not product-specific | [adversarial-review.md](adversarial-review.md) — product-specific risks only |
| Full Rigorous PRD for a simple toggle | Depth misclassified | [depth.md](depth.md) Lite criteria |
| Invented market stats or SLOs | Evidence discipline violated | [global-rules.md](global-rules.md) § Evidence |
| Non-Goals expanded silently during repair | Scope preservation violated | [workflow/repair.md](../workflow/repair.md) § Scope rule |

Maintainer pressure scenarios: [pressure-tests.md](pressure-tests.md).
