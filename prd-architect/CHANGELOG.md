# Changelog — prd-architect

## 1.1.0 — 2026-08-09

### Fixed (prompt-engineering review)

- **Pipeline routing:** Validation and Fundamentally flawed paths stop after Validate → Gate; Begin
  section no longer implies always running Specify → Break → Repair.
- **critique_only:** Break consumes `source_material` when Specify is skipped.
- **SKILL.md NOT table:** "Should we build?" no longer misroutes to domain-comprehension.
- **Description:** SDO-compliant trigger-first wording (no workflow summary in frontmatter).
- **Depth header:** PRD/Review only; Validation uses `Mode:` header exclusively.
- **report-template.md:** Mode-specific minimal templates; no monolithic all-sections skeleton.
- **rationalization-guards.md:** Red flags and rationalization table for discipline failures.
- **Golden evals:** `evals/golden/prd-architect/` (validation-no-mvp, lite-admin-ready, injection-not-ready).
- **examples.md:** Not Ready scenario; Validation short-circuit documented.

## 1.0.0 — 2026-08-09

### Added

- Initial **prd-architect** skill — Classify → Validate → Specify → Break → Repair → Gate pipeline
- Response modes: PRD, Validation, Review (with critique-only path)
- Depth tiers: Lite, Standard, Rigorous with word budgets
- Section triggers, requirements format (FR/BR/NFR/INV/A/AC), correctness rules
- Adversarial review with mandatory Security/Privacy/Operations/Risk perspectives when triggered
- Build Readiness gate (Ready / Ready With Non-Blocking Questions / Not Ready)
- `prd-architect.eval.md` regression suite
- Registry entry, Cursor rule generation, skill-routing and cross-skill-escalation hooks
