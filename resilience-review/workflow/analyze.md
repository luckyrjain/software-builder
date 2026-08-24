---
workflow_version: 1.0
phase: analyze
produces:
  - resilience_findings
  - resilience_conditions
  - evidence_gaps
consumes:
  - resilience_behavior
  - dependency_paths
  - assessment_target
  - evidence
---

# Analyze

Assess every dimension. Never silently omit a dimension; lack of source- and identity-matched
evidence is an explicit UNKNOWN gap.

1. Timeout budgets: end-to-end budget allocation, cancellation, and deadline propagation.
2. Retry policy and amplification: bounded attempts, jitter, retry budgets, and fanout multiplication.
3. Circuit breaking: opening criteria, isolation scope, probe behavior, and safe fallback.
4. Load shedding: overload thresholds, protected work, and client-visible degradation.
5. Backpressure: bounded buffers, producer feedback, and concurrency limits.
6. Queue backlog and poison messages: age/depth alerts, dead-letter/quarantine, replay safety.
7. Duplicate delivery/idempotency: keys, deduplication horizon, and side-effect safety.
8. Downstream outage and latency: bounded waits, fallback correctness, and dependency-path blast radius.
9. Partial-failure consistency: atomicity boundaries, outbox/saga compensation, and observable state.
10. Recovery and reconciliation: repair ownership, replay controls, verification, and convergence.

For current_state PASS, require source evidence from repository or authoritative_host for the exact
candidate revision. Caller-only claims cannot satisfy the requirement. A non-null source environment
must exactly equal the target environment. Source-defined controls may have environment-null evidence;
runtime/config-driven timeout, retry, and circuit-breaker controls require exact environment identity.
