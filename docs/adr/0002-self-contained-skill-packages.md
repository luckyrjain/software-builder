# ADR 0002: Self-contained skill install packages

**Status:** Accepted  
**Date:** 2026-08-08

## Context

Earlier installs copied skill directories with relative links into `docs/skill-framework/`. Installed skills broke when the destination machine did not also have the software-builder checkout, and there was no integrity metadata for support/debugging.

## Decision

- Package each skill via `scripts/package_skill.py` before install: vendored framework files, rewritten local links, and `.software-builder-manifest.json` (source commit + per-file hashes).
- Stage installs in a temp directory, validate the staged package, then atomically `mv` into the target skills directory.
- Restrict installs to `skills.yaml`-registered skill ids (`install_support.py` allowlist).
- Verify packages with `scripts/validate_references.py --installed-package` and `install.sh --verify`.

## Consequences

- **Positive:** Skills are portable across machines without a live repo checkout.
- **Positive:** Validation failures roll back; partial installs do not leave corrupt packages.
- **Negative:** Larger on-disk packages (framework files duplicated per skill).
- **Follow-ups:** Release automation (`make package-release`, tagged GitHub Releases) and expanded install verification in CI.
