# Examples — invocation patterns

Conventions: [examples-conventions](../docs/skill-framework/shared/examples-conventions.md).

## Invocation table

| # | Caller sends | Behavior |
|---|---------------|----------|
| 1 | "Architecture decision approved for Order Service — design the implementation." (full decision: components, events, data model, load numbers, dependencies) | Inputs → Analyze → Report → `Ready to implement` |
| 2 | A build-ready PRD section covering scope, entities, and integration points, with no ambiguity | Inputs → Analyze → Report → `Ready to implement` |
| 3 | Architecture decision whose data model claims `Order` is owned by both `order-service` and `billing-service` | Inputs → Analyze → Report → `Not ready` (contradiction in a required aspect) |
| 4 | Architecture decision with a full component/API/data-model picture but no load or traffic numbers | Inputs → Analyze → Report → `Ready with open questions` (Capacity gap) |
| 5 | Architecture decision describing events and consumers but nothing about downstream-failure handling | Inputs → Analyze → Report → `Ready with open questions` (Failure strategy gap) |
| 6 | "Design the payment system" with no architecture decision or PRD text attached | Inputs HARD STOP — ask for the decision/PRD; Analyze never starts |
| 7 | "Is this architecture decision even sound before we design it?" | Wrong-skill — route to **architecture-review** |
| 8 | "Review this existing API's versioning and pagination design" | Wrong-skill — route to **api-design-review** |
| 9 | "Write me the PRD for this feature first" | Wrong-skill — route to **prd-architect** |

## Scenario: Clean happy path

**Caller:** "Architecture decision approved for Order Service (from architecture-review). Owns order
lifecycle; exposes `POST /orders`; publishes `order.created`/`order.paid`; Postgres-backed; expected peak
500 RPS; downstream billing-service call is async via queue; existing system is greenfield."

**Agent:**
1. Inputs — `architecture_decision_or_prd` present and detailed; no `existing_system_context` (greenfield,
   noted).
2. Analyze — components, APIs, events, data model, state machine, consistency, retries, capacity (500 RPS
   supplied), failure strategy (queue + retry), observability, and rollout plan all derivable with no
   gaps.
3. Report — every section populated, no Open questions → verdict `Ready to implement`.

**Expected fragment:**

```markdown
# System Design Spec — Order Service

**Readiness: Ready to implement**

## Components

| Component | Responsibility | Boundary / owns | Notes |
|-----------|-----------------|------------------|-------|
| `order-service` | Owns order lifecycle | Order aggregate, order events | — |

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Peak RPS | 500 | Stated in architecture decision |
```

## Scenario: Worst state — contradictory data model

**Caller:** "Architecture decision for Order Service: `order-service` owns the `Order` entity for writes;
separately, `billing-service` owns `Order` status updates for refunds."

**Agent:**
1. Inputs — `architecture_decision_or_prd` present.
2. Analyze — Data model check finds `Order` claimed by two owners with no reconciliation stated; flagged
   as a contradiction, not a gap.
3. Report — a required aspect (data model) is internally contradictory → verdict `Not ready`, regardless
   of how complete the other sections are.

**Expected fragment:**

```markdown
**Readiness: Not ready**

## Data model

| Entity | Key fields | Relationships | Owner |
|--------|-----------|-----------------|-------|
| `Order` | — | — | **Contradiction: claimed by both `order-service` and `billing-service` — must be resolved before this design is implementable** |
```

## Scenario: Ready with open questions — multi-finding

**Caller:** "Architecture decision for Notification Service: owns notification dispatch, exposes
`POST /notifications`, publishes `notification.sent`. No traffic numbers given. No mention of what happens
if the downstream SMS provider is unavailable, and no metrics/alerting mentioned."

**Agent:**
1. Inputs — `architecture_decision_or_prd` present; no `existing_system_context`.
2. Analyze — Components/APIs/events/data model derivable cleanly; Capacity has no load data (gap);
   Failure strategy has no downstream-failure handling stated (gap); Observability has no signals stated
   (gap). Three distinct gaps recorded, none silently dropped.
3. Report — no contradictions, but three Open questions → verdict `Ready with open questions`.

**Expected fragment:**

```markdown
**Readiness: Ready with open questions**

## Capacity

| Dimension | Estimate | Basis |
|-----------|----------|-------|
| Peak RPS | Open question | No load data supplied |

## Failure strategy

| Failure mode | Degradation / mitigation |
|--------------|-----------------------------|
| SMS provider unavailable | Open question — not addressed in the supplied architecture decision |

## Observability

| Signal | What's measured |
|--------|-------------------|
| — | Open question — no metrics/alerting stated in the supplied input |
```

## Scenario: Degraded path — no existing-system context

**Caller:** "Architecture decision for a new Search Service replacing the legacy search module — but I
don't have details on the legacy module handy."

**Agent:**
1. Inputs — `architecture_decision_or_prd` present; `existing_system_context` absent (not a HARD STOP —
   it's optional), noted as a gap that will matter for Rollout.
2. Analyze — Components/APIs/events/data model/state machines/consistency/retries derivable from the
   decision alone; Rollout plan check needs the legacy module's current state to sequence a migration and
   cannot derive a safe migration order without it — recorded as an explicit gap, not silently skipped and
   not guessed at.
3. Report — one required-but-underspecified aspect (Rollout plan) → verdict `Ready with open questions`,
   with the gap's cause (missing `existing_system_context`) stated explicitly.

**Expected fragment:**

```markdown
**Readiness: Ready with open questions**

## Rollout plan

| Phase | Scope | Feature flag / migration order |
|-------|-------|----------------------------------|
| — | Open question — no `existing_system_context` supplied; migration order from the legacy search module cannot be derived without it |
```

## Scenario: Cross-skill handoff — API surface ready for contract review

**Caller:** "Architecture decision approved for Checkout API — design it." (Full decision; API surface
comes out fully defined: `POST /checkout`, `GET /checkout/{id}`, pagination and versioning intentionally
left for contract review.)

**Agent:**
1. Inputs → Analyze → Report as in the happy path — verdict `Ready to implement`, API surface section
   populated with concrete endpoints and contracts.
2. Per [SKILL.md § Cross-skill escalation](SKILL.md#cross-skill-escalation), an API surface has been
   defined and is ready for a dedicated contract review.
3. Handoff offered to the caller rather than performed inline (this skill never reviews API contracts
   itself).

**Expected fragment:**

```markdown
**Readiness: Ready to implement**

## APIs

| Endpoint / method | Contract | Consumer(s) | Notes |
|--------------------|----------|-------------|-------|
| `POST /checkout` | Creates a checkout session, returns `checkout_id` | checkout-web | — |
| `GET /checkout/{id}` | Returns checkout session state | checkout-web | — |

---
This design's API surface is defined. Run **api-design-review** next for a dedicated contract review
(compatibility, pagination, idempotency, versioning, authorization, rate limiting) before implementation.
```
