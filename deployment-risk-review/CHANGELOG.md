# Changelog — deployment-risk-review

## 1.1.0 — 2026-08-24

### Changed

- Migrated the producer contract to artifact v2 with typed provenance, assessment context, and
  normalized machine decisions while preserving the human deployment-risk verdict.

## 1.0.0 — 2026-08-22

### Added

- Initial release: pre-ship risk assessment for a single release or change — blast radius,
  migration risk, rollback complexity, dependency risk, and traffic risk, landing on a
  `Risk: Low | Moderate | High | Critical` verdict via the Inputs → Analyze → Report pipeline.
