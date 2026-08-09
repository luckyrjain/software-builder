---
workflow_version: 1.1
phase: specify
produces: {mvp_scope: object, non_goals: list, triggered_sections: list, requirements_draft: object}
consumes:
  required: {request: string, source_material: content, constraints: list, explicit_decisions: list, existing_system: boolean, premise_verdict: string, problem_summary: object, response_mode: string, depth: string, risk_domains: list}
  optional: {}
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

## Section triggers

Build the PRD body using [section-triggers.md](../reference/section-triggers.md). Generate **only**
triggered sections. In **Lite** depth, the Lite preferred list takes precedence unless a trigger is
materially required for safety.

## Requirements

Write per [requirements-format.md](../reference/requirements-format.md):

- necessary, atomic, unambiguous, feasible, testable, consistent, non-duplicative
- implementation-neutral unless constrained
- use decision tables for complex multi-variable business logic
- stable IDs (FR/BR/NFR/INV/A/AC) when ≥8 material requirements or ≥2 delivery teams

## High-risk correctness

When triggered, apply [correctness-rules.md](../reference/correctness-rules.md) — state model, data
rules, invariants, distributed/transactional behavior, permissions, manual controls.

## Diagrams

Use Mermaid only when it materially clarifies flow, state, or sequence. The PRD must remain
understandable without diagrams.

## Traceability

For Standard/Rigorous when ≥10 material requirements, ≥2 teams, or regulated/financial/correctness-sensitive
workflows — trace Problem → Need → Use Case → Requirement → Acceptance Criterion → Success Metric.

## Word budget

Respect depth ceilings in [depth.md](../reference/depth.md) — ceilings, not targets.
