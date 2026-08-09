---
workflow_version: 1.0
phase: repair
produces:
  - repaired_requirements
  - remaining_blockers
  - adversarial_summary
consumes:
  - adversarial_findings
  - scenarios
  - requirements_draft
  - non_goals
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

Update affected: requirements, business rules, flows, state, data rules, permissions, failure handling,
acceptance criteria, risks, assumptions, rollout behavior.

**Scope rule:** if fixing a Critical/High finding requires expanding Non-Goals, surface as an **unresolved
decision** — do not silently expand scope.

## One re-review

Perform **exactly one** independent re-review after repairs. **Do not loop.**

Remaining Critical findings and unsafe High findings → `remaining_blockers` for Gate.

## Appendices

Populate Adversarial Review Summary and Gap Analysis only when material findings add useful context
beyond what is already in the repaired PRD body.
