# Output table schemas
Canonical Markdown table shapes for appendices. **Always include the separator row.** Add data rows at
emit time — never emit a header without `|---|---|`.

## Section triggers
| Section | Trigger |
|---|---|
| Overview | PRD/Review Mode |
| Problem Statement | PRD/Review Mode |
| Product Thesis | Standard/Rigorous unless premise is Strong and uncontested |
| Goals & Non-Goals | PRD/Review Mode |
| Users & Actors | Multiple actors or role-specific behavior |
| Use Cases | Standard/Rigorous, or Lite with multiple workflows |
| MVP Scope | PRD/Review Mode |
| Success Metrics | PRD/Review Mode; each material metric must meet the measurable metric contract |
| Functional Requirements | PRD/Review Mode |
| Requirements Traceability | PRD/Review Mode when material functional requirements exist; `FR-* -> AC-* -> TR-*` |
| Business Rules | Eligibility, limits, calculations, approvals, routing, policy |
| NFRs | Reliability, performance, security, compatibility, availability, scale |
| End-to-End Flow | Multiple steps, systems, actors, or meaningful branching |
| State Model | Lifecycle, approvals, async processing, retries, cancellations |
| UX States | Loading/pending/error/degraded states materially affect users |
| Data Requirements | Persistent/shared data affects behavior |
| Data Invariants | Correctness depends on uniqueness, ordering, balances, state, etc. |
| Roles & Permissions | Actors have different capabilities |
| Manual Controls | Overrides, recovery, privileged intervention |
| Failure Handling | Failures materially affect outcome |
| Correctness & Reconciliation | Transactions, money, inventory, multi-writer, async consistency |
| Security / Privacy / Abuse | Sensitive data, auth, exposure, fraud, misuse |
| Operational Readiness | Production change; ownership/support/recovery/capacity/dependency readiness matters |
| Observability Requirements | Production change; define required metrics/logs/traces/alerts/dashboard/correlation |
| Performance / Scale | Throughput, latency, capacity or volume matters |
| SLOs | Reliability target materially affects product/contract |
| Dependencies | External or cross-team dependencies |
| Cost Impact | New infrastructure, material traffic/storage growth, or paid dependency changes economics |
| Experimentation | Problem/solution hypothesis remains unvalidated |
| Rollout / Rollback | Production/existing-system change where staged delivery or reversal materially affects risk |
| Migration / Backward Compatibility | Existing system or API/event/schema/data/config/client behavior changes |
| API / Event / Schema Impact | API, event, or schema contract changes |
| Data / Privacy Impact | Personal/sensitive data, retention, or access changes |
| Assumption Register | Consequential assumptions exist; Lite may use a compact in-body subsection |
| Change Impact | Review Mode on an existing product/system |
| Risks | Material risks exist |
| Open Questions | Material unresolved decisions exist |

## Assumption ledger (Standard/Rigorous)
| ID | Assumption | Evidence | Impact If Wrong | Validation |
|---|---|---|---|---|
Evidence levels: Verified | Supported | Unverified | **Risky**

## Requirements traceability
| Requirement | Acceptance Criteria | Test Requirement | Evidence / Source |
|---|---|---|---|
Use one row per material `FR-*`; every row must link at least one `AC-*` and one `TR-*`.

## Adversarial Review Summary
| Severity | Perspective | Finding | Scenario | Resolution |
|---|---|---|---|---|

## Gap Analysis
| Area | Gap | Scenario | Impact | Resolution |
|---|---|---|---|---|

## Material Changes (Review Mode)
| Area | Before | After | Reason |
|---|---|---|---|

## Research provenance (when external research is cited)
| Claim / conclusion | Source | Confidence |
|---|---|---|

Use for regulation, market, competitor, or standards claims that materially shaped requirements.
Do not cite assumptions as evidence.
