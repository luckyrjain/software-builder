# PRD Architect — report templates

Emit **only triggered sections** per [section-triggers.md](reference/section-triggers.md). **Never** copy
an entire template wholesale — add a section only when its trigger fired.

Full rules: [reference/output-contract.md](reference/output-contract.md).

---

## PRD Mode (including repaired Review body)

**Start with:** `Depth: <Lite|Standard|Rigorous> — <brief reason>`

### Lite (typical shape)

```markdown
Depth: Lite — <reason>

# <Product / Feature Name>

## Overview
## Problem Statement
## Goals & Non-Goals
## MVP Scope
## Functional Requirements
## Key Failure / Edge Cases
## Acceptance Criteria
## Risks
## Assumptions
<!-- short in-body list when needed -->

## Build Readiness
**Verdict:** Ready | Ready With Non-Blocking Questions | Not Ready
<rationale>
```

Add sections from [section-triggers.md](reference/section-triggers.md) when material (e.g., Roles &
Permissions, Failure Handling, Security / Privacy / Abuse).

### Standard / Rigorous

Same header pattern. Add triggered sections only — e.g., State Model, Data Invariants, End-to-End Flow,
Correctness & Reconciliation, Rollout / Migration. Use FR-/BR-/NFR-/INV-/AC- IDs when required per
[requirements-format.md](reference/requirements-format.md).

### Appendices (when triggered)

- **Decisions & Constraints** — resolved decisions and mandatory constraints only
- **Assumptions** — table when ≥3 consequential or Risky assumptions (Standard/Rigorous)
- **Unresolved Questions** — only non-empty categories
- **Adversarial Review Summary** / **Gap Analysis** — only when material context beyond inline fixes

---

## Review Mode extras

After the repaired PRD body:

```markdown
## Material Changes

| Area | Before | After | Reason |
```

Include **Change Impact** when reviewing an existing product/system.

---

## Review Mode — critique only (`critique_only`)

**Do not** output a repaired PRD. Emit:

```markdown
Depth: <depth> — <reason>

## Findings
<!-- severity-tagged, by perspective -->

## Gap Analysis

| Area | Gap | Scenario | Impact | Resolution |

## Build Readiness
**Verdict:** ...
```

---

## Validation Mode

**Start with:** `Mode: Validation — <brief reason>` — **no Depth line.**

```markdown
Mode: Validation — <reason>

## Problem Assessment
## Premise Verdict
## Key Assumptions
## Alternatives
## Material Risks
## Recommendation
## Evidence Needed Next
```

Do not include MVP, Functional Requirements, or Build Readiness unless the user explicitly requests a
full PRD or readiness verdict.
