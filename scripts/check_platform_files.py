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

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.registry.canonical_manifest import LEGACY_PROJECTION_FILENAMES, legacy_projection_path
from scripts.registry.cli import optional_layer_paths

# A root-agnostic stand-in, so the inventory below is a list of repository-relative paths
# (what this check reports and what its callers assert on) while still being *derived* from
# the gates it protects rather than restated beside them.
_TEMPLATE_ROOT = Path("/repository-root")


def _relative(path: Path) -> str:
    return path.relative_to(_TEMPLATE_ROOT).as_posix()


# Every file whose absence silently disables something: the optional-layer gates in
# scripts/registry/cli.py, plus the three legacy contract projections `make generate`
# maintains. Derived from both sources so a new layer or projection joins this inventory
# automatically instead of waiting for someone to remember.
REQUIRED_PLATFORM_FILES: tuple[str, ...] = tuple(
    sorted(
        {_relative(path) for path in optional_layer_paths(_TEMPLATE_ROOT)}
        | {
            _relative(legacy_projection_path(_TEMPLATE_ROOT, section))
            for section in LEGACY_PROJECTION_FILENAMES
        }
    )
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
