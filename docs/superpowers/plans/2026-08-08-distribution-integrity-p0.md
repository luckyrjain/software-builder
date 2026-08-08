# Distribution Integrity P0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the critical installed-skill packaging defect so user-wide installs remain self-contained after the source checkout is removed.

**Architecture:** `scripts/package_skill.py` copies the skill tree, vendors the full `docs/skill-framework/` directory when any framework link is present, rewrites in-skill links to package-local paths, writes `.software-builder-manifest.json`, and validates with `scripts/validate_references.py --installed-package`.

**Tech Stack:** Bash (`scripts/install.sh`), Python 3.12, pytest, existing Makefile lint targets.

## Global Constraints

- Keep imports at top of module (no inline imports).
- Do not expand scope into `skills.yaml` registry or transactional installer in this plan.
- Installed-package validation enforces `docs/skill-framework/` and skill-local links; optional cross-skill/repo doc links are tolerated.

---

### Task 1: Packaging + validation scripts — **DONE**

- `scripts/reference_utils.py`, `scripts/package_skill.py`, `scripts/validate_references.py`
- `scripts/check_requirements_lock.py`
- Tests in `scripts/tests/`

### Task 2: Installer + CI integration — **DONE**

- `scripts/install.sh` calls packager + validator
- `make verify-install`, `make lint-requirements-lock` added to `make lint`
- `scripts/tests/test_install_integration.sh`

### Task 3: Quick wins — **DONE**

- `make setup` uses `requirements.lock`
- `lint-framework` loops cover all 22 skills
- Framework README documents real packaging behavior
- `CODEOWNERS` covers `requirements.lock`

**Spec:** `docs/superpowers/specs/2026-08-08-distribution-integrity-design.md`
