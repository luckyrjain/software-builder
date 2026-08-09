# Output contract

The PRD body must contain **all accepted fixes**. Appendices are explanatory, not required to
reconstruct the specification.

## PRD Mode

**Start with:** `Depth: <depth> — <brief reason>`

**Always output:**

- Final PRD (repaired body with all accepted fixes inline)
- Build Readiness

**Include when triggered** ([section-triggers.md](section-triggers.md)):

### Decisions & Constraints

Only resolved user decisions and mandatory/verified constraints. Do not duplicate assumptions.

### Assumptions

Consequential uncertain propositions and validation plans.

### Unresolved Questions

Only non-empty categories: Blocking Before Build | Required Before Launch | Can Resolve During
Implementation.

### Adversarial Review Summary

Only when material findings add useful context beyond the PRD body.

| Severity | Perspective | Finding | Scenario | Resolution |

### Gap Analysis

Only when material gaps add useful context beyond the PRD body.

| Area | Gap | Scenario | Impact | Resolution |

## Review Mode

**Start with:** `Depth: <depth> — <brief reason>`

**Always output:**

- Repaired PRD
- Material Changes
- Build Readiness

**Material Changes table:**

| Area | Before | After | Reason |

**Include when triggered:** Change Impact; Decisions & Constraints; Assumptions; Unresolved Questions;
Adversarial Review Summary; Gap Analysis (same rules as PRD Mode).

**Critique only:** If the user explicitly requests review without rewrite — output findings, gap
analysis, and readiness instead of a repaired PRD.

## Validation Mode

**Start with:** `Mode: Validation — <brief reason>`

**Output (always, in order):**

1. Problem Assessment
2. Premise Verdict (Strong | Reasonable but unvalidated | Weak | Fundamentally flawed)
3. Key Assumptions
4. Alternatives
5. Material Risks
6. Recommendation
7. Evidence Needed Next

Do not produce a full PRD unless requested.

## Build Readiness

Authoritative verdict — exactly one:

- **Ready** — implementation can safely begin
- **Ready With Non-Blocking Questions** — implementation can begin; identified decisions remain
- **Not Ready** — material blockers remain

Hard gates: [workflow/gate.md](../workflow/gate.md).

## Calibration reference

| Input | Expected |
|-------|----------|
| "Add an admin control that lets support temporarily disable new user registrations." | Depth: Lite; ~1 page PRD + Build Readiness only; authorized admin, enable/disable, audit log, registration state, acceptance criteria |
| "Is an AI support chatbot worth building to reduce tickets?" | Mode: Validation; Premise: Reasonable but unvalidated; 7-section output; recommend simpler validation before full build |

Template skeleton: [report-template.md](../report-template.md).
