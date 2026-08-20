---
workflow_version: 1.3
phase: 2-evidence
produces:
  review_evidence: object
  inspection_plan: object
  review_metrics: object
consumes:
  required:
    change_identity: object
    inspection_plan: object
    coverage_unable_to_inspect: list
    findings: list
    portable_suggestions: list
    portable_questions: list
    review_metrics: object
    jira_ac_table: list
  optional:
    root_cause_groups: list
  conditional: {}
---

# Phase 2 evidence finalization

Run immediately after Phase 2 coverage review and before the Phase 2→3 gate for every non-listing review. This
step is read-only.

Load `../reference/review-coverage-contract.yaml` and
`../reference/review-coverage-execution.md` §Phase 2 evidence.

Require every triggered inspection surface to already be finalized by Phase 2 coverage review as `complete` or
`unable`; never convert a triggered surface to `not_applicable` here. Use `coverage_unable_to_inspect` as the
canonical unavailable list. Do not silently drop an unavailable surface merely to improve the final status.

Map rich PRR output into the closed shared review-evidence v1 envelope without adding PRR-only fields to portable
finding entries:

- `defect` comes only from the typed `findings` list and preserves the existing PRR ID.
- `suggestion` comes only from typed `portable_suggestions` produced by Phase 2 coverage review.
- `question` comes only from typed `portable_questions` produced by Phase 2 coverage review.

For suggestions/questions, derive the deterministic `PRS-*` / `PRQ-*` ID from each typed `{summary, evidence}`
entry using `review-coverage-contract.yaml`; do not rediscover or reconstruct non-defect prose here. Portable entries
contain exactly `{id, category, summary, evidence}`. Keep severity, PRR category, confidence, blast radius,
grouping, and OEDR/OAR in the existing rich review metadata.

Set portable `review_mode: exhaustive` only for an explicit exhaustive/full-pass request; otherwise use `normal`.
Incremental and retrospective lifecycle state stays outside this closed portable field.

Build final `review_evidence`, then call
`pr-review/scripts/validate_review_coverage.py` → `validate_review_coverage(...)` with the current identity,
requirements reference when present, and `conflict_resolution_occurred=True` whenever the review cycle included
merge/rebase conflict resolution after the prior evidence was produced. Conflict resolution invalidates prior
review evidence even when the normalized effective patch and other identity fields are otherwise freshness-compatible.
Any validation error blocks the Phase 2→3 posting path. Never make validation pass by weakening a trigger, dropping
an unavailable annotation, changing a mandatory flag, rewriting evidence text, or silently removing a typed
suggestion/question whose evidence is valid.

When final `review_evidence.inspection_status` is `partial` or `unable`, set
`review_metrics.review_complete: false` before leaving this phase. This deliberately feeds the existing Phase 3
incomplete-review confirmation gate: a partial review must never inherit the "review and post" auto-confirm path.
Do not set the flag back to true here when inspection status is complete; preserve any earlier incomplete boundary
(stop-search, pagination/file cap, or other Phase 2 reason).

Pass the validated `review_evidence`, final `inspection_plan`, and updated `review_metrics` to the Phase 2→3 gate.
