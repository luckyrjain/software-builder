---
workflow_version: 1.2
phase: repair
produces:
  repaired_requirements: object
  remaining_blockers: list
  adversarial_summary: object
  success_metrics: list
  assumption_register: list
  requirements_traceability: object
  engineering_impact: object
consumes:
  required:
    adversarial_findings: list
    scenarios: list
    requirements_draft: object
    non_goals: list
    success_metrics: list
    assumption_register: list
    requirements_traceability: object
    engineering_impact: object
  optional: {current_state_evidence: object}
  conditional: {}
---

# Repair — incorporate validated findings

## Accept a finding only when

- scenario is credible
- issue is not already addressed
- impact is **material** ([global-rules.md](../reference/global-rules.md))
- reasoning does not depend on invented facts
- fix does not unnecessarily expand scope or prescribe implementation

## Repair priority

| Severity | Action |
|----------|--------|
| Critical | Must repair or escalate to Blocking Before Build |
| High | Must repair or Blocking Before Build if implementation unsafe |
| Medium | Repair when useful |
| Low | Repair only when clearly valuable |

Repair the complete PRD contract, not just requirement prose. Update affected requirements, business rules,
flows, state, data rules, permissions, failure handling, acceptance criteria, success metrics, assumptions,
`FR -> AC -> TR` traceability, and triggered engineering-impact sections. When repairing an existing-system
proposal, preserve the observed baseline from `current_state_evidence`; a repair may change the proposal but
must not rewrite current-state evidence to make the finding disappear.

After repairs:

- re-check success metrics for baseline/target/timeframe/measurement-source completeness;
- ensure consequential assumptions retain stable IDs, owner, validation path, impact, and status;
- regenerate traceability for changed requirements/acceptance criteria and leave no material orphan;
- re-evaluate rollout/rollback, operational readiness, compatibility, API/event/schema, data/privacy, cost,
  and observability triggers after the repaired behavior; and
- keep unresolved Critical/High issues in `remaining_blockers` with the affected contract area.

**Scope rule:** if fixing a Critical/High finding requires expanding Non-Goals, surface as an **unresolved
decision** — do not silently expand scope.

## Re-review

Perform exactly one fresh adversarial re-review of the repaired complete contract. Do not reuse the original
finding list as proof. New Critical/High findings remain blockers; do not loop indefinitely inside Repair.
