---
workflow_version: 1.1
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
finding entries. Portable entries contain exactly `{id, category, summary, evidence}`, with category one of
`defect`, `suggestion`, or `question`. Keep severity, PRR category, confidence, blast radius, grouping, and
OEDR/OAR in the existing rich review metadata.

Set portable `review_mode: exhaustive` only for an explicit exhaustive/full-pass request; otherwise use `normal`.
Incremental and retrospective lifecycle state stays outside this closed portable field.

Build final `review_evidence`, then call
`pr-review/scripts/validate_review_coverage.py` → `validate_review_coverage(...)` with the current identity and
requirements reference when present. Any error blocks the Phase 2→3 posting path. Never make validation pass by
weakening a trigger, dropping an unavailable annotation, changing a mandatory flag, or rewriting evidence text.

Pass the validated `review_evidence` and final `inspection_plan` to the Phase 2→3 gate.
