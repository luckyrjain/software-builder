---
workflow_version: 1.0
phase: candidates
produces:
  - candidate_set
consumes:
  - evidence_ledger
  - hotspot_observations
  - evidence_gaps
---

# Candidates — form evidence-gated hypotheses

Create a candidate only when multiple relevant observations support a specific, bounded architecture
hypothesis. A filename, size, repetition, requested refactor, or history signal alone is insufficient.

Each candidate must contain every field below. Mark a field unknown only when the candidate remains useful
to falsify; otherwise do not create it.

| Field | Required content |
|-------|------------------|
| ID | Stable local identifier |
| Scope | Bounded paths, symbols, and affected callers |
| Friction | Observed developer or behavioral cost |
| Evidence | Concrete observations and their sources |
| Contract/seam | Affected public contract, ownership boundary, or seam |
| Hypothesis | The smallest change in responsibility or direction that may relieve friction |
| Locality | Expected effect on coordinated change and ownership |
| Caller simplification | Specific caller behavior that could become simpler, or `none shown` |
| Testing improvement | Production-observable test benefit, or `none shown` |
| Abstraction cost | New indirection, concepts, ownership, and maintenance burden |
| Migration risk | Compatibility, rollout, and removal risks |
| ADR interaction | Relevant ADR alignment, conflict, or `none found` |
| Confidence | Evidence-backed confidence with stated limits |

Return 3–7 candidates only when supported. Fewer candidates, including zero, are valid outcomes. Never
rank a speculative candidate above a well-supported absence of a candidate, and never perform a refactor.
