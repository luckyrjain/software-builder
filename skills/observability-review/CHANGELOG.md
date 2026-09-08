# Changelog — observability-review

## 1.1.0 — 2026-08-24

### Changed

- Migrated the producer contract to artifact v2 with typed provenance, assessment context, and
  normalized machine decisions while preserving the human observability verdict.

## 1.0.0 — 2026-08-22

### Added

- Initial release: evaluates a service's metrics, logs, tracing, dashboards, alerts, SLOs, and
  correlation-ID propagation for coverage and gaps against caller-supplied material, via the
  Inputs → Analyze → Report pipeline, producing `OBSERVABILITY_REVIEW_REPORT.md`.
