---
workflow_version: 1.0
phase: report
produces:
  - change_impact_report
consumes:
  - change_classes
  - impacted_surfaces
  - evidence_gaps
---

# Report

Emit the canonical `change_impact_report` artifact with its fixed v1 fields. Use `PARTIAL` or
`UNKNOWN` coverage when required repository or exact SCM evidence is unavailable, and retain all
material unknowns and evidence references in the result.
