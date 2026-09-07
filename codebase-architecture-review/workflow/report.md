---
workflow_version: 1.0
phase: report
produces:
  - CODEBASE_ARCHITECTURE_REVIEW.md
  - codebase_architecture_report
consumes:
  - review_scope
  - review_budget
  - history_status
  - evidence_ledger
  - evidence_gaps
  - retained_candidates
  - falsification_results
---

# Report — emit CODEBASE_ARCHITECTURE_REVIEW.md

Build the report using [reference/report-format.md](../reference/report-format.md). Its document form is
`CODEBASE_ARCHITECTURE_REVIEW.md`; its typed machine form is `codebase_architecture_report`. Emit both as
the read-only response/artifact—do not write either into the repository. Before rendering, also read
[reference/html-report.md](../reference/html-report.md); it governs the ephemeral visual HTML companion.

The report must show the scope, budgets consumed, history status, evidence ledger, evidence gaps, each
candidate's complete fields, and falsification result. State why candidates were rejected or why none are
valid. Set `recommended_next_skill: null` exactly; do not direct or invoke a downstream skill. Registered
`escalation_targets` are optional human-visible handoff offers only: present any bounded offer for a
separate user-authorized invocation, but never emit it in this typed result or dispatch it automatically.

Every retained candidate's card must state its depth, deletion test result, recommendation strength,
dependency category, and both a before model and an after model. A zero-candidate report may omit candidate
cards entirely. `mock-only` never independently justifies retaining a seam. The report also renders, by
default, one ephemeral HTML visual companion in OS temporary storage, and every retained candidate must also
get a visual card there; see [reference/html-report.md](../reference/html-report.md) for the full contract,
including its two named degraded-rendering exceptions and the exclusion of that path from the durable
`codebase_architecture_report` payload and from `skill_result.artifacts`.

Render all repository and caller content under the safe-output boundary. Preserve observed evidence,
inference, and proposals as distinct categories. Omit claims unsupported in degraded history mode rather
than presenting them as low-confidence history facts.
