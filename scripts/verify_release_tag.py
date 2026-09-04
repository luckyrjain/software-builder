#!/usr/bin/env python3
"""Verify a git tag is the one scripts/release_contract.yaml maps VERSION to."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from release_contract import release_tag_for_version
from release_info import read_distribution_version

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_release_tag")
    parser.add_argument("tag", help="git tag name (e.g. v1.4.0)")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    try:
        expected_version = read_distribution_version(args.repo_root)
        # The tag shape lives in the release contract, not here: one declaration for
        # the validator that checks it renders and the gate that requires it.
        expected_tag = release_tag_for_version(
            expected_version, args.repo_root / "scripts" / "release_contract.yaml"
        )
    except (OSError, ValueError) as exc:
        # OSError (not just ValueError) so a VERSION file that exists but isn't readable
        # (e.g. a permission error) prints a clean error instead of an uncaught traceback.
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.tag != expected_tag:
        print(
            f"error: tag {args.tag!r} does not match VERSION file ({expected_version!r}); "
            f"the release contract maps it to {expected_tag!r}",
            file=sys.stderr,
        )
        return 1

    print(f"ok: tag {args.tag} matches VERSION {expected_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
