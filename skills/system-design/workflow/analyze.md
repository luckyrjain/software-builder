---
workflow_version: 1.0
phase: analyze
produces:
  - components
  - apis
  - events
  - data_model
  - state_machines
  - consistency
  - retries
  - capacity
  - failure_strategy
  - observability
  - rollout_plan
consumes:
  - architecture_decision_or_prd
  - existing_system_context
---

# Analyze — evaluate the implementation-oriented design

Run each of the following checks concretely against `architecture_decision_or_prd` (and
`existing_system_context` where relevant). Every check either produces a finding or an explicit gap — no
check is silently skipped.

- **Components** — identify component boundaries and responsibilities implied or stated by the input;
  flag any responsibility that is ambiguous or claimed by more than one component.
- **APIs** — derive the API surface (endpoints/methods or RPCs) each component exposes, its contract
  (request/response shape, at least at a summary level), and its consumers.
- **Events** — derive event topics/schemas, producers, and consumers where the design involves
  asynchronous communication; note if the design is fully synchronous (no events expected).
- **Data model** — identify entities, their key fields, relationships, and which component owns each
  entity; flag contradictory ownership claims.
- **State machines** — for each entity with lifecycle behavior, derive its states and transitions,
  including what triggers each transition.
- **Consistency** — for each data/write boundary, determine whether strong or eventual consistency
  applies and why (single-writer vs cross-service, latency/availability trade-off stated or inferable).
- **Retries & idempotency** — for each write operation, determine whether it is idempotent (and how — key,
  natural idempotency, none) and what retry/backoff strategy applies.
- **Capacity** — derive rough sizing (RPS, storage growth, connection counts) only where the input
  supplies load/traffic data or a stated scale target; otherwise record as an Open question — never
  invent numbers.
- **Failure strategy** — for each external/downstream dependency named in the input, determine what
  happens on failure (degrade, queue, circuit-break, fail closed) and how that's decided.
- **Observability** — determine what signals (metrics/logs/traces) the design calls for or implies are
  needed to tell the system is healthy.
- **Rollout** — derive a phased rollout plan: migration order, feature flags, dual-write/dual-read
  periods, and dependency on `existing_system_context` where a migration from a current state is implied.

An evidence gap for any individual check (the input doesn't supply enough to answer it) is recorded as an
explicit gap on that check, never silently skipped — this feeds Report's "Open question" handling.
