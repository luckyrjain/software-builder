#!/usr/bin/env python3
"""Assert every load-bearing platform file is present in the repository.

scripts/registry/cli.py's `_validate_for_generate`/`_validate_all` gate several validation
layers (host-adapter, capability-catalog, capability-family, P1, release-contract) behind
`<path>.is_file()` checks. Those checks were originally scaffolding for the incremental rollout
of each file; a repository-agnostic hard requirement can't replace them there without breaking
the deliberately minimal fixtures several registry tests use (see scripts/tests/test_registry.py).

This script closes the actual regression risk instead: it hard-asserts, against the real
checked-out repository only, that every file those gates key off of still exists -- so a bad
merge or an accidental `git rm` of one of these permanent files fails CI loudly instead of
silently disabling the validation layer that depends on it.
"""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED_PLATFORM_FILES: tuple[str, ...] = (
    "scripts/registry/host_contracts.yaml",
    "scripts/registry/capability_catalog.yaml",
    "scripts/registry/capability_families.yaml",
    "scripts/registry/eval_contracts.yaml",
    "docs/skill-framework/shared/runtime-contract.md",
    "docs/skill-framework/shared/host-adapter-contract.md",
    "docs/skill-framework/shared/eval-contract.md",
    "scripts/release_contract.yaml",
)


def missing_platform_files(repo_root: Path) -> list[str]:
    return [
        relpath
        for relpath in REQUIRED_PLATFORM_FILES
        if not (repo_root / relpath).is_file()
    ]


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    missing = missing_platform_files(repo_root)
    if missing:
        print(
            "error: required platform file(s) missing -- "
            "scripts/registry/cli.py's validation gates silently skip the layer(s) "
            "these files back:",
            file=sys.stderr,
        )
        for relpath in missing:
            print(f"  - {relpath}", file=sys.stderr)
        return 1
    print(f"ok: all {len(REQUIRED_PLATFORM_FILES)} required platform files are present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
