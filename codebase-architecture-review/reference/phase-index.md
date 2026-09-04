# Phase index

Read one `workflow/` file per active phase; do not bulk-load the workflow or references.

| Step | Read now | Produces |
|------|----------|----------|
| **Scope** | [workflow/scope.md](../workflow/scope.md) | `review_scope`, `review_budget`, `history_status` |
| **Evidence** | [workflow/evidence.md](../workflow/evidence.md) | `evidence_ledger`, `hotspot_observations`, `evidence_gaps` |
| **Candidates** | [workflow/candidates.md](../workflow/candidates.md) | `candidate_set` |
| **Falsify** | [workflow/falsify.md](../workflow/falsify.md) | `falsification_results`, `retained_candidates` |
| **Report** | [workflow/report.md](../workflow/report.md) | `CODEBASE_ARCHITECTURE_REVIEW.md`, `codebase_architecture_report` |

Reference loads: [lazy-load-index.md](lazy-load-index.md).

## Quick paths

| Caller situation | Behavior |
|------------------|----------|
| Bounded existing code with inspectable evidence | Scope → Evidence → Candidates → Falsify → Report |
| Git history unavailable | Continue degraded; omit churn/co-change claims and lower dependent confidence |
| No candidate survives falsification | Emit an evidence-backed zero-candidate report |
| Proposed future architecture | Stop this review and use `architecture-review` instead |
