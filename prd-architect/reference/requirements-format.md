# Requirements format

## Identifiers

For **Lite**, concise bullets are acceptable.

For **Standard/Rigorous**, use stable identifiers when ≥8 material requirements **or** ≥2 delivery teams
depend on the document:

| Prefix | Type |
|--------|------|
| FR-## | Functional Requirement |
| BR-## | Business Rule |
| NFR-## | Non-Functional Requirement |
| INV-## | Invariant |
| A-## | Assumption |
| AC-FR##-## | Acceptance Criterion |

## Quality bar

Every material requirement must be:

- necessary
- atomic
- unambiguous
- feasible
- testable
- internally consistent
- non-duplicative
- implementation-neutral unless constrained

Rewrite requirements that fail these tests.

## Acceptance criteria

Critical requirements require testable acceptance criteria. Each must be:

- observable
- specific
- testable
- linked to the intended requirement
- inclusive of important negative behavior

Example:

```
FR-03 — An authorized support agent must be able to suspend an active customer account.
BR-02 — A suspended account must not initiate new transactions.
AC-FR03-01 — Given an active account and an authorized support agent, when the agent suspends the
  account, the account state becomes Suspended.
AC-FR03-02 — Given a Suspended account, when the customer attempts to create a new transaction, the
  request is rejected.
```

## Decision tables

For complex multi-variable business logic, use a decision table instead of nested prose.

## Traceability

When any of the following apply, maintain traceability:

- ≥10 material requirements
- ≥2 delivery teams
- regulated, financial, or correctness-sensitive workflow

Trace: Problem / Outcome → User Need → Use Case → Requirement → Acceptance Criterion → Success Metric.

Challenge material requirements without a defensible upstream need.

## Rollout and measurement

When triggered, define: rollout stages; migration; backward compatibility; cohorts; feature controls;
monitoring; rollback; kill conditions. **Do not invent thresholds.**

Define metrics for:

- **Outcome** — whether the product solved the intended problem
- **Guardrails** — harmful side effects
- **Operations** — system health when operational health matters

Avoid vanity metrics.
