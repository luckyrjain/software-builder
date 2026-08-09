#!/usr/bin/env python3
"""Verify git tag matches VERSION before release."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from release_info import read_distribution_version

ROOT = Path(__file__).resolve().parents[1]
_TAG_RE = re.compile(r"^v(?P<version>\d+\.\d+\.\d+)$")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="verify_release_tag")
    parser.add_argument("tag", help="git tag name (e.g. v1.4.0)")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    match = _TAG_RE.match(args.tag)
    if not match:
        print(f"error: tag must match vMAJOR.MINOR.PATCH, got {args.tag!r}", file=sys.stderr)
        return 1

    expected = read_distribution_version(args.repo_root)
    actual = match.group("version")
    if actual != expected:
        print(
            f"error: tag version {actual!r} does not match VERSION file ({expected!r})",
            file=sys.stderr,
        )
        return 1

    print(f"ok: tag {args.tag} matches VERSION {expected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
