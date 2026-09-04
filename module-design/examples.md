# Examples — module-design

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation

Invoke `module-design` ambiently for a bounded design of one concrete module in an existing repository.
It is read-only and report-only: inspect the bounded module scope and repository evidence, emit a design
report, and never change repository state or implement or refactor automatically.

| Caller sends | Behavior |
|-------------|----------|
| "Design the `src/payments/charge.py` module boundary. Here are its callers, tests, gateway client, and failure traces." | Inputs → Design → Report with an evidence-backed module contract and seam decision |
| "The `auth/session` module has three callers that branch on Redis errors. Design its contract from these files." | Identifies caller leakage, error contract, state/concurrency implications, and migration steps |
| "Should we add `PaymentGateway` here? The only reason is to mock the SDK in a unit test." | Rejects the mock-only interface; keeps a production-facing test surface or documents an earned boundary |
| "There may be a repository or service abstraction between checkout and billing; compare options from these call paths." | Provides two materially different designs if the interface remains uncertain, then recommends one |
| "Design all order, billing, inventory, and notification modules." | Scope expansion — offer `system-design`; do not invoke it automatically |
| "Decide whether our event-driven architecture is safe at projected scale." | Wrong scope — offer `architecture-review`; do not invoke it automatically |
| "Design a module" with no path, responsibility, callers, tests, or repository evidence | HARD STOP — ask for concrete `module_scope` and `repository_evidence` |

## Example: adapter earned by a real boundary

**Evidence:** `charge.py` calls a payment SDK from three paths; SDK exceptions and field names leak into
each caller; existing contract tests assert a domain `Declined` error.

**Result:** define a `ChargeProcessor` contract owned by the payments module, with an SDK adapter that
translates request/response/error shapes. Preserve the domain error invariant, identify retry-safe state,
and test the production-facing contract. The adapter is justified by a translation responsibility, not by
the number of implementations.

## Example: unresolved interface choice

**Evidence:** a reporting caller and a checkout caller need different read shapes, but the supplied
evidence does not establish whether that difference is durable.

**Result:** compare a narrow query contract against separate module-owned projections as two materially
different designs. State caller impact, dependency direction, test surface, migration cost, and the missing
future-change evidence as an unresolved question; do not invent a shared pass-through interface.
