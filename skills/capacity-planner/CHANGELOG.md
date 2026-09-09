# Changelog — capacity-planner

## 1.1.0 — 2026-08-24

### Changed

- Migrated the producer contract to artifact v2 with typed provenance, assessment context, and
  normalized machine decisions while preserving the human capacity verdict.

## 1.0.0 — 2026-08-22

### Added

- Initial release: turns historical demand data + a forecast horizon into RPS/concurrency, CPU, memory,
  database, queue, storage, and replica-count capacity requirements, via a linear Inputs → Analyze →
  Report pipeline producing `CAPACITY_PLAN.md` with an explicit Headroom verdict and stated assumptions.
