# Output contract

The PRD body must contain **all accepted fixes**. Appendices are explanatory, not required to
reconstruct the specification.

Table column schemas and canonical section triggers: [output-tables.md](output-tables.md) — **always
include separator rows** when emitting tables. Existing-system evidence rules:
[current-state-evidence-contract.yaml](current-state-evidence-contract.yaml).

## PRD Mode

**Start with:** `Depth: <depth> — <brief reason>`

### Normal path

**Always output:**

- Final PRD (repaired body with all accepted fixes inline)
- measurable Success Metrics for material outcomes
- material `FR-* -> AC-* -> TR-*` Requirements Traceability
- Build Readiness

Consequential assumptions use a stable Assumption Register. Existing/production-system engineering sections
are emitted only when their canonical trigger fires: Rollout / Rollback, Operational Readiness, Migration /
Backward Compatibility, API / Event / Schema Impact, Data / Privacy Impact, Cost Impact, and Observability
Requirements. A fired trigger with incomplete required fields is a readiness blocker, not a reason to omit the
section.

### Fundamentally flawed premise

Stop normal PRD generation. Output:
- Validation-style 7-section assessment (same sections as Validation Mode)
- **Build Readiness: Not Ready**
Produce a full PRD only when the user **explicitly** requested one despite the flawed premise.

**Include when triggered** ([section-triggers.md](section-triggers.md)):

### Decisions & Constraints

Only resolved user decisions and mandatory/verified constraints. Do not duplicate assumptions.

### Assumption Register

Consequential uncertain propositions and validation plans with stable `A-*` IDs. Table schema:
[output-tables.md](output-tables.md) § Assumption ledger. Do not emit an empty register.

### Unresolved Questions

Only non-empty categories: Blocking Before Build | Required Before Launch | Can Resolve During
Implementation.

### Research provenance

When external research materially influenced a requirement, constraint, risk, market assertion,
regulatory conclusion, or recommendation, include the Research provenance table from
[output-tables.md](output-tables.md). **Do not cite assumptions as evidence.**

### Adversarial Review Summary

Only when material findings add useful context beyond the PRD body. Schema:
[output-tables.md](output-tables.md) § Adversarial Review Summary.

### Gap Analysis

Only when material gaps add useful context beyond the PRD body. Schema:
[output-tables.md](output-tables.md) § Gap Analysis.

## Review Mode

**Start with:** `Depth: <depth> — <brief reason>`

### Improve / fix (default)

**Always output:**

- Repaired PRD, including measurable material metrics and material `FR-* -> AC-* -> TR-*` traceability
- Material Changes ([output-tables.md](output-tables.md) § Material Changes)
- Build Readiness

For existing systems, preserve observed current-state evidence separately from proposed/repaired behavior and
re-run all engineering-impact triggers after Repair.

### Critique only (`critique_only`)

- Findings (severity-tagged)
- Gap Analysis ([output-tables.md](output-tables.md) § Gap Analysis)
- Build Readiness
- **No** repaired PRD body

**Material Changes table:**

| Area | Before | After | Reason |
|---|---|---|---|

**Include when triggered:** Change Impact; Decisions & Constraints; Assumption Register; Unresolved Questions;
Research provenance; Adversarial Review Summary; and the engineering-impact sections from the canonical
trigger matrix (same rules as PRD Mode when a repaired PRD is emitted).

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

Research provenance may be included when external research materially influenced the assessment. Do not run
Specify/Break/Repair merely to manufacture PRD-only metrics, traceability, or engineering sections.

Do not produce a full PRD unless requested.

## Build Readiness

Authoritative verdict — exactly one:

- **Ready** — implementation can safely begin
- **Ready With Non-Blocking Questions** — implementation can begin; identified decisions remain
- **Not Ready** — material blockers remain

Hard gates: [workflow/gate.md](../workflow/gate.md).

Template skeleton: [report-template.md](../report-template.md).
