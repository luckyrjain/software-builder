# Examples — domain-modeling

Conventions: [examples-conventions](../../docs/skill-framework/shared/examples-conventions.md).

## Invocation

Invoke `domain-modeling` ambiently whenever a term, relationship, or decision under active discussion is
fuzzy, conflicts with `CONTEXT.md`, or crystallizes into a decision worth recording. It is read-only and
report-only: inspect the session and repository evidence, emit a proposal, and never write `CONTEXT.md`,
`CONTEXT-MAP.md`, or `docs/adr/*.md`, or implement anything automatically.

| # | Caller sends | Resolves to | Notes |
|---|-----------------|---------------|-------|
| 1 | "Your glossary defines 'cancellation' as an Order state, but I mean cancelling one line item." | Inputs → Challenge → Report with a named conflict and two proposed canonical terms | Happy path |
| 2 | "We just decided: refunds always go through the original payment method, never store credit — because store credit created a reconciliation gap last quarter." | Challenge finds a real decision point; Report drafts an ADR | ADR path |
| 3 | "What happens if a Customer cancels an Order that's already partially shipped?" | Challenge invents/records the edge-case scenario and its answer | Scenario path |
| 4 | "You're saying 'account' — do you mean the Customer or the User?" | Challenge sharpens the fuzzy term into two canonical ones | Sharpening |
| 5 | "Just edit CONTEXT.md to add this term, don't bother with a report." | Rejected — report-only; proposal emitted, no direct write | Boundary rule |
| 6 | "Map our entire domain model, we have no CONTEXT.md yet." | Wrong scope — offer `domain-comprehension` | Wrong-skill row |
| 7 | "That Order-cancellation decision — now design the CancellationPolicy module's interface." | Wrong scope — offer `module-design` | Cross-skill handoff |
| 8 | "Is our event-driven cancellation flow safe at 10x scale?" | Wrong scope — offer `architecture-review` | Wrong-skill row |

## Example: glossary conflict surfaced, not silently resolved

**Evidence:** `CONTEXT.md` defines `Cancellation` as "an Order transitions to the Cancelled state." The
session describes cancelling a single line item while the rest of the Order ships normally.

**Result:**

```
## Terminology findings

| Term | Existing definition | Session usage | Conflict/gap | Proposed canonical definition |
|------|----------------------|----------------|---------------|--------------------------------|
| `Cancellation` | "an Order transitions to the Cancelled state" | cancelling one line item, order continues | existing definition covers whole-Order only | Split into `OrderCancellation` (existing) and `LineItemCancellation` (new) |
```

No definition is silently kept or silently overwritten — both are named, and a split term is proposed.

## Example: a real decision drafts an ADR

**Evidence:** the session states refunds must always return to the original payment method, rejects
store credit as an alternative, and cites a reconciliation gap as the reason.

**Result:**

```
## Proposed ADR

- ID: 0006 (next available)
- Title: Refunds return to original payment method only
- Status: Proposed
- Context: Store credit refunds created a reconciliation gap last quarter.
- Decision: All refunds route to the original payment method; store credit is not offered.
- Consequences: Refund flow no longer needs a store-credit ledger; edge case for expired original
  payment methods remains an open question.
- Rejected alternatives: Store credit refund (caused the reconciliation gap).
```

## Example: no decision, no fabricated ADR

**Evidence:** the session only restates that "an Order has a Customer" — already correct and uncontested
in both `CONTEXT.md` and the code.

**Result:** `adr_readiness: false`. The report's Proposed ADR section states "No ADR proposed this
session — no decision point crystallized," rather than inventing one to fill the section.

## Degraded path: no CONTEXT.md exists yet

**Evidence:** the repository has no `CONTEXT.md` and no `CONTEXT-MAP.md`.

**Result:** `existing_context` is empty; the report proceeds with the session's own statements as the only
evidence source, and the Proposed CONTEXT.md patch section proposes creating the file for the first time
— it does not create it directly.
