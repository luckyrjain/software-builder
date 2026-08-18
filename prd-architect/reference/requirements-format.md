# Requirements format

## Identifiers

Every **material functional requirement** uses a stable identifier at every depth so engineering
verification is deterministic:

| Prefix | Type |
|--------|------|
| FR-## | Functional Requirement |
| AC-FR##-## | Acceptance Criterion linked to an FR |
| TR-FR##-## | Test / verification requirement linked to an AC/FR |

For Standard/Rigorous, or whenever ≥8 material requirements or ≥2 delivery teams depend on the document,
also use stable identifiers for the broader requirement set:

| Prefix | Type |
|--------|------|
| BR-## | Business Rule |
| NFR-## | Non-Functional Requirement |
| INV-## | Invariant |
| A-## | Consequential Assumption (always stable when included) |

Lite may keep prose compact, but it does not replace material `FR-*`, `AC-*`, or `TR-*` identifiers with
unlinked bullets.

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

## Acceptance criteria and verification

Every material `FR-*` requires at least one testable `AC-*`, and every material `AC-*` requires at least one
`TR-*` describing how the criterion will be verified. Each acceptance criterion must be:

- observable
- specific
- testable
- linked to the intended requirement
- inclusive of important negative behavior

A `TR-*` is a verification obligation, not necessarily a specific test-framework implementation. It may map
to unit, integration, contract, end-to-end, operational, security, migration, or manual evidence as
appropriate.

Example:

```
FR-03 — An authorized support agent must be able to suspend an active customer account.
BR-02 — A suspended account must not initiate new transactions.
AC-FR03-01 — Given an active account and an authorized support agent, when the agent suspends the
  account, the account state becomes Suspended.
TR-FR03-01 — Verify the authorized suspension path and persisted state transition with an integration test.
AC-FR03-02 — Given a Suspended account, when the customer attempts to create a new transaction, the
  request is rejected.
TR-FR03-02 — Verify the rejected transaction path for a Suspended account, including the user-visible error.
```

## Decision tables

For complex multi-variable business logic, use a decision table instead of nested prose.

## Traceability

Maintain `FR-* -> AC-* -> TR-*` for every material functional requirement in PRD/Review Mode.

When any of the following also apply, maintain the broader product trace:

- ≥10 material requirements
- ≥2 delivery teams
- regulated, financial, or correctness-sensitive workflow

Trace: Problem / Outcome → User Need → Use Case → Requirement → Acceptance Criterion → Success Metric.

Challenge material requirements without a defensible upstream need.

## Rollout and measurement

When triggered, define: rollout stages; migration; backward compatibility; cohorts; feature controls;
monitoring; rollback; kill conditions. **Do not invent thresholds.**

Every material success metric records baseline, target, timeframe, and measurement source. If a baseline is
not currently known, mark it Unknown and define the measurement action instead of inventing a number.

Define metrics for:

- **Outcome** — whether the product solved the intended problem
- **Guardrails** — harmful side effects
- **Operations** — system health when operational health matters

Avoid vanity metrics.
