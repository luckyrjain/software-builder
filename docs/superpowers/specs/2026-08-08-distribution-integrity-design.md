# Distribution integrity — self-contained skill packages

**Date:** 2026-08-08  
**Status:** Approved for P0 implementation  
**Source:** August 2026 repository review (`software-builder-latest-main-full-review-2026-08-07.md`) findings #1, #4, #6, #14

## Problem

`scripts/install.sh` copies only a skill directory (`cp -r`) while skill Markdown links to normative
files under `docs/skill-framework/`. Installed skills therefore lose prompt-injection, routing,
confidence, and other shared contracts when the `software-builder` checkout is not open.

## Goal

Make user-wide installs self-contained: every local Markdown link required by an installed skill
resolves after the source checkout is removed.

## Non-goals (this phase)

- Full `skills.yaml` registry (#12)
- Transactional installer with rollback (#5)
- Generated host adapters (#10)
- Behavioral eval harness (#7)

## Approach: compiled self-contained bundles

At install time:

1. Copy the skill directory into the destination.
2. Scan all Markdown in the package for references to `docs/skill-framework/`.
3. Transitively vendor referenced framework files into `<skill>/docs/skill-framework/`.
4. Rewrite Markdown links to package-local relative paths.
5. Write `.software-builder-manifest.json` (skill name, source SHA, file hashes, framework files).
6. Validate zero dangling local Markdown links before completing install.

`scripts/validate_references.py` supports `--source-tree` (repo checkout) and
`--installed-package <path>` modes for CI.

## Acceptance criteria

- Install `unit-test-creator` into an empty temporary HOME.
- Delete/move the source checkout.
- `validate_references.py --installed-package <dest>` returns 0.
- Manifest records source commit SHA.
- CI runs an install integration test on every PR.
- Framework README no longer claims installed skills symlink to the repo.

## Quick wins bundled in P0

- `make setup` installs `requirements.lock` (hash-pinned, matches CI).
- CI/Makefile fails when `requirements.txt` and `requirements.lock` drift.
- `lint-framework` enforcement loops include all 22 skills (fix 16-vs-22 drift).
- Stale "all 16 skills" prose updated.
- `make verify-install` runs the install integration test.
