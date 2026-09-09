---
workflow_version: 1.0
phase: falsify
produces:
  - falsification_results
  - retained_candidates
consumes:
  - candidate_set
  - evidence_ledger
  - evidence_gaps
---

# Falsify — try to disprove every candidate

Actively test every candidate against counterevidence before it may appear as retained. Look for callers
that already use a stable contract, tests that protect the alleged seam, a single legitimate owner,
compatibility obligations, ADR constraints, an alternative source of friction, or an abstraction cost that
exceeds the claimed benefit.

For every candidate, record:

| Check | Required result |
|-------|-----------------|
| Counterevidence sought | Concrete callers, tests, docs, ADRs, config, or history queried |
| Result | Supported, contradicted, inconclusive, or blocked, with sources |
| Decision | Retain, downgrade, or reject |
| Confidence effect | Explain the resulting confidence change, including degraded-history limits |

Reject candidates whose central friction is not reproduced by evidence, whose proposed boundary conflicts
with an ADR or public contract, or whose only benefit is mockability. An inconclusive result is not a pass:
downgrade it or remove it. Candidates cannot bypass falsification because of urgency, file size, or a caller
request.

Also test every candidate's Matt-specific claims:

- Did the deletion test show caller complexity scattering, or did the proposed module merely rename a pass-through?
- Does the before model show a real interface/seam problem rather than a large file?
- Does the after model reduce interface surface while concentrating behavior?
- Is the recommendation strength consistent with the evidence and history status?
- Is `mock-only` the sole reason for the seam? If yes, reject the candidate.
