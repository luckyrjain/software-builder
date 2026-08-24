# Examples — resilience-review

## Proposed design

Review a proposed checkout design with a documented end-to-end timeout budget, bounded retry budget,
dead-letter queue, idempotency key, and reconciliation process. Supply the checkout-to-payments path
and source-defined design evidence. A proposed-state assessment can be Approved without a candidate
revision when the evidence is otherwise sufficient.

## Current candidate

Review the exact candidate revision for checkout in production. Supply repository or authoritative-host
evidence through a runtime-owned assessment_context trust handoff. A caller claim labelled repository
does not satisfy current-state PASS.

## Runtime-configured timeout

When timeout, retry, or circuit-breaker behavior comes from runtime/config input, identify that
dimension in runtime_config_dimensions and provide evidence for the exact target environment. A
missing or mismatched environment produces an explicit UNKNOWN condition.
