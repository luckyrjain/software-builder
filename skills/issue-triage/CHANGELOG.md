# Changelog — issue-triage

## 1.0.0 — 2026-09-10

### Added

- Initial ambient, read-only issue-triage skill: classifies one or more raw incoming issues, bugs, or
  feature requests by category, severity, evidence-gated duplicate-of, and a recommended owning skill
  or squad; flags incident-shaped issues for `incident-rca` instead of routine backlog handling; and
  proposes report-only `ISSUE_TRIAGE_REPORT.md` / `issue_triage_report` output. Never writes a label,
  state transition, or tracker field directly.
