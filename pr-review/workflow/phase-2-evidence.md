---
workflow_version: 1.2
phase: 2-evidence
produces:
  review_evidence: object
  inspection_plan: object
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
`pr-review/scripts/validate_review_coverage.py` → `validate_review_coverage(...)` with the current identity and
requirements reference when present. Any error blocks the Phase 2→3 posting path. Never make validation pass by
weakening a trigger, dropping an unavailable annotation, changing a mandatory flag, rewriting evidence text, or
silently removing a typed suggestion/question whose evidence is valid.

Pass the validated `review_evidence` and final `inspection_plan` to the Phase 2→3 gate.
