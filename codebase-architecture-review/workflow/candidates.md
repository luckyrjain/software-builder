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
| Depth | Current interface surface versus implementation depth; identify leaked caller knowledge |
| Deletion test | What disappears versus what scatters if the module/abstraction is removed |
| Recommendation strength | Exactly `Strong`, `Worth exploring`, or `Speculative` with evidence limit |
| Dependency category | Exactly `in-process`, `local-substitutable`, `ports-and-adapters`, or `mock-only` |
| Before model | Structural model of current modules, interface, leakage, and seam |
| After model | Structural model of proposed responsibility concentration and seam |

`mock-only` cannot support retaining a seam by itself: a dependency category of `mock-only` is a warning
classification, never evidence that a seam should be created or kept.

Return 3–7 candidates only when supported. Fewer candidates, including zero, are valid outcomes. Never
rank a speculative candidate above a well-supported absence of a candidate, and never perform a refactor.
