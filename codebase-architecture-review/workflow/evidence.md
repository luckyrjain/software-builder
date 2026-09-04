---
workflow_version: 1.0
phase: evidence
produces:
  - evidence_ledger
  - hotspot_observations
  - evidence_gaps
consumes:
  - review_scope
  - review_budget
  - history_status
---

# Evidence — collect observations before hypotheses

Create an evidence ledger with source, observation, relevance, and confidence. Inspect implementation,
callers, tests, dependency/configuration declarations, ADRs, and documentation when they bear on the
bounded question. Select at most three hotspots only when preliminary evidence makes deeper inspection
useful.

Classify every statement as one of:

| Class | Meaning |
|-------|---------|
| Observed | Directly supported by a path, symbol, test, configuration, ADR, or permitted history fact |
| Inference | Reasoned from observations; state the reasoning and confidence |
| Gap | Missing, inaccessible, or ambiguous information that limits a conclusion |

History may indicate repeated coordinated changes, but never proves a design flaw. In degraded history mode,
do not claim churn, co-change, ownership movement, or trend evidence. Corroborate any history signal with
current code, callers, tests, or an ADR before treating it as candidate evidence.

Use the shared [codebase-design-principles.md](../../docs/skill-framework/shared/codebase-design-principles.md)
to evaluate contract surface, locality, behavioral leverage, seams, cohesion, coupling, dependency direction,
test surface, abstraction cost, and navigability. No observation alone creates a candidate.
