# PRD Architect — report template

Canonical output skeleton. Generate **only triggered sections** — never empty or N/A blocks.
Full rules: [reference/output-contract.md](reference/output-contract.md) · Section triggers:
[reference/section-triggers.md](reference/section-triggers.md).

---

## PRD Mode / Review Mode (repaired PRD body)

```markdown
Depth: <Lite|Standard|Rigorous> — <brief reason>

# <Product / Feature Name>

## Overview
<!-- Triggered: PRD/Review -->

## Problem Statement
<!-- Triggered: PRD/Review -->

## Product Thesis
<!-- Standard/Rigorous unless premise Strong and uncontested -->

## Goals & Non-Goals
<!-- Triggered: PRD/Review -->

## Users & Actors
<!-- Multiple actors or role-specific behavior -->

## Use Cases
<!-- Standard/Rigorous, or Lite with multiple workflows -->

## MVP Scope
<!-- Triggered: PRD/Review — Smallest safe release -->

### Should Have
### Later
### Non-Goals

## Functional Requirements
<!-- FR-## when ≥8 material requirements or ≥2 teams -->

## Business Rules
<!-- BR-## when eligibility, limits, calculations, routing -->

## Non-Functional Requirements
<!-- NFR-## when reliability, security, scale matter -->

## End-to-End Flow
<!-- Multiple steps, systems, actors, branching -->

## State Model
<!-- Lifecycle, async, retries, cancellations -->

## UX States
<!-- Loading/pending/error/degraded materially affect users -->

## Data Requirements
## Data Invariants
<!-- INV-## when correctness depends on uniqueness, balances, ordering -->

## Roles & Permissions
## Manual Controls

## Failure Handling
## Correctness & Reconciliation

## Security / Privacy / Abuse

## Operations / Observability

## Performance / Scale
## SLOs

## Dependencies
## Cost & Economics
## Experimentation

## Rollout / Migration
## Rollback / Kill Criteria

## Success Metrics

## Assumptions
<!-- Lite: short in-body subsection; Standard/Rigorous: table when consequential -->

## Risks

## Open Questions
<!-- Only non-empty categories -->

## Acceptance Criteria
<!-- AC-FR##-## linked to requirements when traceability applies -->
```

---

## PRD Mode appendices (when triggered)

### Build Readiness

```markdown
## Build Readiness

**Verdict:** Ready | Ready With Non-Blocking Questions | Not Ready

<one-paragraph rationale tied to hard gates in workflow/gate.md>
```

### Decisions & Constraints
<!-- Resolved user decisions and mandatory/verified constraints only — not assumptions -->

### Adversarial Review Summary
<!-- Only when material findings add useful context -->

| Severity | Perspective | Finding | Scenario | Resolution |

### Gap Analysis
<!-- Only when material gaps add useful context -->

| Area | Gap | Scenario | Impact | Resolution |

---

## Review Mode extras

### Material Changes

| Area | Before | After | Reason |

### Change Impact
<!-- When Review Mode applies to an existing product/system -->

---

## Validation Mode

```markdown
Mode: Validation — <brief reason>

## Problem Assessment
## Premise Verdict
<!-- Strong | Reasonable but unvalidated | Weak | Fundamentally flawed -->

## Key Assumptions
## Alternatives
## Material Risks
## Recommendation
## Evidence Needed Next
```
