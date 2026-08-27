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
  - freshness_snapshot
---

# Emit the production_readiness_report artifact

## Final freshness re-check

Immediately before emitting the report, re-read the candidate's head identity, CI status, and
approval state and compare them against the snapshot taken at the start of Collect evidence. Any
regression since that first read (the head changed, CI went from green to red, an approval was
dismissed) is a `FAIL` on its own, independent of every other dimension — a `READY` verdict must
reflect the candidate as it stands right now, not as it stood when evidence collection began. A
snapshot that can't be reconfirmed (missing head identity, CI/approvals status that couldn't be
re-read) is `UNKNOWN`, never a silent pass-through to the verdict already computed.

Build one `production_readiness_report` v1 payload per [reference/report-format.md](../reference/report-format.md):

`title`, `assessment_target`, `source_revision`, `build_provenance_ref`, `criticality`, `verdict`,
`dimension_statuses`, `operational_evidence`, `blockers`, `conditions`, `waivers`,
`required_actions`, `evidence_refs`.

- `blockers` — every dimension that set `NOT_READY` (a required `FAIL`).
- `conditions` — every dimension that set `CONDITIONAL`, plus any valid recorded waiver (which does
  not itself change the verdict — see below).
- `waivers` — any valid caller-supplied waiver, recorded with its own provenance
  (`accepted_by`, `evidence_ref`, `expires_at`). A waiver never changes the computed verdict or a
  dimension's underlying evidence-authority trace — verdict derivation is fixed per
  [reference/gate-policy.md § Verdict precedence](../reference/gate-policy.md#verdict-precedence)
  with no waiver exception, so a waived `FAIL`, `UNKNOWN`, or `CONDITIONAL` dimension still blocks
  the verdict exactly as an unwaived one would.
- `required_actions` — one line per blocker/condition naming what would need to change to improve the
  verdict; never left implicit.

Apply the safe rendered-output boundary in
[reference/report-format.md § Safe rendered-output boundary](../reference/report-format.md#safe-rendered-output-boundary)
to every field sourced from the PR/MR title, description, commit messages, or a child review's
free-text evidence before it renders. This skill never posts, merges, or deploys — emitting
`production_readiness_report` is the entire deliverable.
