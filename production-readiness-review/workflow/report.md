---
workflow_version: 1.0
phase: report
produces:
  - production_readiness_report
consumes:
  - verdict
  - dimension_statuses
  - operational_evidence
  - dispatch_log
  - assessment_target
  - criticality
  - source_revision
  - build_provenance_ref
---

# Emit the production_readiness_report artifact

Build one `production_readiness_report` v1 payload per [reference/report-format.md](../reference/report-format.md):

`title`, `assessment_target`, `source_revision`, `build_provenance_ref`, `criticality`, `verdict`,
`dimension_statuses`, `operational_evidence`, `blockers`, `conditions`, `waivers`,
`required_actions`, `evidence_refs`.

- `blockers` — every dimension that set `NOT_READY` (a required `FAIL`).
- `conditions` — every dimension that set `CONDITIONAL`, plus any explicitly recorded waiver.
- `waivers` — any caller-supplied waiver applied to a dimension, recorded with its own provenance;
  a waiver never upgrades a dimension's underlying evidence-authority trace, it only changes whether
  that dimension's status still blocks the verdict.
- `required_actions` — one line per blocker/condition naming what would need to change to improve the
  verdict; never left implicit.

Apply the safe rendered-output boundary in
[reference/report-format.md § Safe rendered-output boundary](../reference/report-format.md#safe-rendered-output-boundary)
to every field sourced from the PR/MR title, description, commit messages, or a child review's
free-text evidence before it renders. This skill never posts, merges, or deploys — emitting
`production_readiness_report` is the entire deliverable.
