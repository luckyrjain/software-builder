# PRD Architect — report templates

Emit **only triggered sections** per [section-triggers.md](reference/section-triggers.md). **Never** copy
an entire template wholesale — add a section only when its trigger fired.

Full rules: [reference/output-contract.md](reference/output-contract.md). For an existing system, ingest
current-state evidence according to [current-state-evidence-contract.yaml](reference/current-state-evidence-contract.yaml)
and preserve observed facts separately from proposed behavior.

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
## Success Metrics
## Functional Requirements
## Key Failure / Edge Cases
## Acceptance Criteria
## Requirements Traceability
## Risks

## Build Readiness
**Verdict:** Ready | Ready With Non-Blocking Questions | Not Ready
<rationale>
```

Every success metric must be measurable using the canonical table in
[output-tables.md](reference/output-tables.md) § Success metrics: baseline, target, timeframe, measurement
source, and a baseline measurement action when the baseline is Unknown. Trace every material functional
requirement as `FR-* -> AC-* -> TR-*`; orphan requirements or acceptance criteria block Build Readiness.
When consequential assumptions exist, add a stable **Assumption Register** using the canonical ledger,
including Owner and Status.

Add sections from [section-triggers.md](reference/section-triggers.md) when material (e.g., Roles &
Permissions, Failure Handling, Security / Privacy / Abuse, Assumption Register).

### Standard / Rigorous

Same header pattern. Add triggered sections only — e.g., State Model, Data Invariants, End-to-End Flow,
Correctness & Reconciliation. Material functional requirements always use `FR-*`, `AC-*`, and `TR-*`; use
`BR-*`, `NFR-*`, and `INV-*` IDs when required per
[requirements-format.md](reference/requirements-format.md).

For existing or production systems, emit the following when their contract trigger fires:

```markdown
## Rollout / Rollback
<!-- rollout strategy, success signal, abort signal; rollback trigger, mechanism, data compatibility, verification -->

## Operational Readiness
<!-- ownership, runbook, alerts, dashboards, support path, capacity, dependency readiness -->

## Migration / Backward Compatibility
<!-- evaluate API/event/schema/data/config/client compatibility; for breaking changes include migration plan, rollout sequence, rollback constraints -->

## API / Event / Schema Impact
<!-- before contract, after contract, compatibility, consumers, migration -->

## Data / Privacy Impact
<!-- classification, access, retention, audit, compliance review; only when personal/sensitive data, retention, or access changes -->

## Cost Impact
<!-- baseline, expected delta, measurement plan; only when new infrastructure, material traffic/storage growth, or paid-dependency change fires -->

## Observability Requirements
<!-- metrics, logs, traces, alerts, dashboard, correlation -->
```

### Appendices (when triggered)

- **Decisions & Constraints** — resolved decisions and mandatory constraints only
- **Assumption Register** — when consequential assumptions exist; use the canonical ledger in
  [output-tables.md](reference/output-tables.md) so ID, impact, validation, owner, and status are preserved
- **Requirements Traceability** — `FR-* -> AC-* -> TR-*` matrix for engineering-verifiable requirements
- **Unresolved Questions** — only non-empty categories
- **Adversarial Review Summary** / **Gap Analysis** — only when material context beyond inline fixes

---

## Review Mode extras

After the repaired PRD body:

```markdown
## Material Changes

| Area | Before | After | Reason |
```

Include **Change Impact** when reviewing an existing product/system. Re-run compatibility, rollout,
operational-readiness, cost, privacy, and observability triggers against the repaired state.

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
