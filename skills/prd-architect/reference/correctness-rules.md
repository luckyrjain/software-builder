# High-risk correctness rules

Apply only when triggered by risk domain or section triggers.

## State

Define:

- initial state
- valid states
- terminal states
- allowed transitions
- invalid transitions
- transition actor/trigger
- retry / failure / cancellation behavior

## Data

Define relevant:

- source of truth
- identifiers
- uniqueness
- ordering
- immutability
- retention / deletion
- sensitive fields
- audit fields

## Invariants

State conditions that must remain true regardless of execution path. Use INV-## identifiers in
Standard/Rigorous when applicable.

## Distributed / transactional correctness

Consider when async, multi-system, or money/inventory paths exist:

- idempotency
- duplicate requests
- concurrency
- partial completion
- consistency
- finality
- discrepancy detection
- reconciliation
- correction
- auditability

## Permissions / manual controls

Define who may: view; create; modify; approve; reject; cancel; retry; override; recover.

For privileged actions define: authorization; approval if required; reason capture; audit trail; recovery
to normal operation.

## Change impact

In Review Mode for an existing product/system, determine whether material changes affect: user flows;
business rules; state; APIs; integrations/events; data; permissions; security; metrics; operations;
migration; tests; documentation.

Do not treat a local requirement change as isolated when downstream impact exists.
