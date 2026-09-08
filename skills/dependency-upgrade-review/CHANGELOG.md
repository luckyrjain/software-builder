# Changelog — dependency-upgrade-review

## 1.1.0 — 2026-08-24

### Changed

- Migrated the producer contract to artifact v2 with typed provenance, assessment context, and
  normalized machine decisions while preserving the human dependency verdict.

## 1.0.0 — 2026-08-22

### Added

- Initial release: reviews a dependency/framework version bump for breaking changes, CVEs, API
  differences, transitive dependency impact, and rollout risk, delivering a single verdict via the
  Inputs → Analyze → Report pipeline.
