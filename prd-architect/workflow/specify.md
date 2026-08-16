---
workflow_version: 1.4
phase: specify
produces:
  mvp_scope: object
  non_goals: list
  triggered_sections: list
  requirements_draft: object
  success_metrics: list
  assumption_register: list
  requirements_traceability: object
  engineering_impact: object
consumes:
  required:
    request: string
    source_material: content
    constraints: list
    explicit_decisions: list
    existing_system: boolean
    premise_verdict: string
    problem_summary: object
    response_mode: string
    depth: string
    risk_domains: list
  optional:
    current_state_evidence: object
  conditional: {}
---

# Specify — scope and triggered PRD sections

## Scope tiers

| Tier | Content |
|------|---------|
| **MVP** | Smallest safe release delivering meaningful value or testing the central hypothesis |
| **Should Have** | Important but non-blocking for first release |
| **Later** | Useful but deferrable |
| **Non-Goals** | Explicit exclusions — **authoritative** |

For weakly validated ideas, consider whether validation should precede full implementation:
prototype, manual workflow, fake-door, shadow mode, internal pilot, limited cohort, A/B test.

## Current-state baseline

For `existing_system=true`, begin from `current_state_evidence` when available. Keep observed behavior,
ownership, contracts, and source revisions separate from proposed changes. A proposed PRD may change current
state, but every such change must be explicit and traceable to the baseline. Do not silently reinterpret an
`Observed` fact as future intent.

## Section triggers

Build the PRD body using [section-triggers.md](../reference/section-triggers.md) and
[current-state-evidence-contract.yaml](../reference/current-state-evidence-contract.yaml). Generate **only**
triggered sections. In **Lite** depth, the Lite preferred list takes precedence unless a trigger is materially
required for correctness, safety, compatibility, operability, privacy, cost, or observability.

Evaluate these engineering triggers explicitly for existing/production systems:

- rollout/rollback
- operational readiness
- migration/backward compatibility
- API/event/schema impact
- data/privacy impact
- material cost impact
- observability requirements

Record the trigger result in `engineering_impact`; absence of a rendered section must mean the trigger did
not fire, not that it was forgotten.

## Requirements

Write per [requirements-format.md](../reference/requirements-format.md):

- necessary, atomic, unambiguous, feasible, testable, consistent, non-duplicative
- implementation-neutral unless constrained
- use decision tables for complex multi-variable business logic
- every material functional requirement gets stable `FR-*`, `AC-*`, and `TR-*` identifiers so engineering traceability is possible at every depth
- use stable `BR-*`, `NFR-*`, and `INV-*` IDs when the existing requirements-format thresholds apply; consequential assumptions always use stable `A-*` IDs

For every material `FR-*`, create or identify at least one `AC-*`, and create the corresponding `TR-*`
verification requirement. Maintain `FR-* -> AC-* -> TR-*` in `requirements_traceability`. An orphaned material
FR or AC is a Build Readiness blocker; do not defer it to implementation.

## Success metrics

For PRD/Review, every material success metric must define `metric`, `baseline`, `target`, `timeframe`, and
`measurement_source`. A qualitative aspiration without a measurable target is not a success metric. If a
baseline is genuinely unavailable, mark it Unknown and include an evidence-gathering action; do not invent a
number.

## Assumption register

Track consequential assumptions with stable `A-*` IDs and the fields in the current-state evidence contract:
statement, impact, validation, owner, and status. Keep facts out of the assumption register. Risky OPEN
assumptions that affect MVP safety/viability feed the Gate verdict.

## High-risk correctness

When triggered, apply [correctness-rules.md](../reference/correctness-rules.md) — state model, data
rules, invariants, distributed/transactional behavior, permissions, manual controls.

## Diagrams

Use Mermaid only when it materially clarifies flow, state, or sequence. The PRD must remain
understandable without diagrams.

## Traceability

For Standard/Rigorous when ≥10 material requirements, ≥2 teams, or regulated/financial/correctness-sensitive
workflows, additionally trace Problem → Need → Use Case → Requirement → Acceptance Criterion → Success Metric.
The `FR -> AC -> TR` engineering trace remains mandatory for material functional requirements in all PRD/Review
depths.

## Word budget

Respect depth ceilings in [depth.md](../reference/depth.md) — ceilings, not targets.
