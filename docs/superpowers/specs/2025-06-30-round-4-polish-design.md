# Round 4 polish — cross-skill report parity

**Date:** 2025-06-30  
**Branch:** `cursor/skill-improvements-r3`  
**Approach:** Single pass (Approach A)

## Scope

Mirror k8s Human Report polish on **incident-rca**, light **pr-review** conclusion block, framework smoke-test compliance, Makefile lint symmetry, SETUP portability, and verification.

### 1. incident-rca human-report parity

- `report-template.md` + `workflow/phase-5.md`: `## Conclusion`, `## Risks` (`Overall:` lead), hypothesis confidence as band + numeric + `Basis:` bullets
- Ban `Type ACT` / agent mode in report body; post-actions in chat only (`SKILL.md`, phase-5)
- `reference/thresholds.md`: display format aligned with shared confidence bands
- `examples.md`: golden fragments for deploy regression + multi-cause scenarios

### 2. pr-review light touch

- `report-template.md` section map + `reference/executive-summary.md`: explicit `## Conclusion` after Executive Summary

### 3. Framework compliance

- `incident-rca/reference/smoke-test.md`: invocation, failure diagnosis, pressure-tests link, script self-test
- `k8s-overprovisioning-datadog/reference/smoke-test.md`: `## Invocation` + failure diagnosis
- `docs/skill-framework/shared/smoke-test-conventions.md`: fix k8s path → `reference/smoke-test.md`
- `incident-rca/SKILL.md`: `## Framework` block mirroring pr-review

### 4. Makefile lint symmetry

- `grep -q 'cross-skill-escalation'` in `lint-incident-rca` and `lint-pr-review-skill` (match k8s)

### 5. Portability

- `k8s-overprovisioning-datadog/SETUP.md`, `pr-review/SETUP.md`: replace org-specific GitLab URLs with placeholders + calibration notes

### 6. Verify

- `make lint` (all targets)

## Out of scope

- Graph schema / INV changes
- README.org-wide URL sweep (SETUP files only)
- Push to remote
