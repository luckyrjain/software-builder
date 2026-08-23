---
workflow_version: 1.0
phase: report
produces:
  - SYSTEM_DESIGN_SPEC.md
consumes:
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
---

# Report — derive verdict, build SYSTEM_DESIGN_SPEC.md

Derive the Readiness verdict with fixed, worst-first precedence:

1. **Not ready** — a required aspect (components, APIs/events, data model, or failure strategy) is missing
   entirely or internally contradictory (e.g. conflicting entity ownership, a component boundary claimed
   twice).
2. **Ready with open questions** — the design is otherwise coherent but one or more aspects (capacity,
   rollout order, observability, an existing-system integration point) could not be derived from the
   supplied input and are recorded as explicit Open questions.
3. **Ready to implement** — every section has a concrete answer; no Open questions remain.

Build per [reference/report-format.md](../reference/report-format.md).
