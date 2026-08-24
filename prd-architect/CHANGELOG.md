# Changelog — prd-architect

## Unreleased

### Changed

- A ready PRD now hands off to `system-design` before architecture validation.

### Added

- Existing-system current-state handoff contract compatible with `domain-comprehension` machine artifacts,
  including multi-repo source revisions and preservation of observed state.
- Engineering-verifiable PRD fields for measurable success metrics, stable assumption registers,
  `FR-* -> AC-* -> TR-*` traceability, rollout/rollback, operational readiness, backward compatibility,
  API/event/schema impact, data/privacy, cost, and observability.

### Changed

- Specify, Break, Repair, and Gate now carry the new metric/assumption/traceability/engineering-impact
  fields through the complete route rather than treating them as template-only guidance.
- Canonical section triggers, depth guidance, requirements format, output contract, and report templates
  now use the same engineering-readiness rules.

### Fixed

- Gate now escapes/fences untrusted Markdown structure, redacts sensitive excerpts, and reserves the
  skill-authored Build Readiness section so source material cannot forge a verdict.
- Gate's safe-output rules now have an executable reference renderer covering adversarial Markdown
  structure and sensitive-data redaction.
- Phase input contracts now declare every required, optional, and conditional mapping explicitly.
- Workflow lint now closes the field-type and phase-frontmatter vocabularies and reports malformed
  YAML mapping keys deterministically.
- Existing-system path is forced when current-state/domain handoff evidence is present so untrusted
  `existing_system=false` cannot skip freshness/baseline gates; Specify refuses stale PRD baselines;
  assumption ledger and unknown-baseline metric fields align with the readiness contract.

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
