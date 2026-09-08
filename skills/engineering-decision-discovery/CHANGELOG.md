# Changelog — engineering-decision-discovery

## 1.0.0 — 2026-09-05

### Added

- Initial ambient, interactive, read-only, evidence-backed decision-discovery skill: typed
  `decision_scope` inputs, a dependency-aware decision tree, a frontier algorithm that never asks a
  dependent question ahead of an unresolved prerequisite, a recommend-then-ask interaction loop with
  explicit user ownership of every decision, an unattended `BLOCKED` rule for a remaining material
  frontier, and report-only `ENGINEERING_DECISION_RECORD.md` output with no ADR write.
