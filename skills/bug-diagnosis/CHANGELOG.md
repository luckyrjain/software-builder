# Changelog — bug-diagnosis

## 1.0.0 — 2026-09-09

### Added

- Initial ambient, read-only bug-diagnosis skill: confirms a minimal repro from evidence, forms
  candidate root causes and actively falsifies each one, and emits report-only
  `BUG_DIAGNOSIS_REPORT.md` / `bug_diagnosis_report` output — including every hypothesis tried,
  rejected or survived, with its evidence. Never edits source, tests, or configuration to fix the
  bug, and never commits, pushes, or opens a PR.
