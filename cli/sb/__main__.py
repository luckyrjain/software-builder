#!/usr/bin/env python3
"""Entry point for the `sb` console script."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_version


def _package_version() -> str:
    try:
        return _installed_version("software-builder-cli")
    except PackageNotFoundError:
        return "unknown (not installed)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sb")
    parser.add_argument(
        "--version", action="version", version=f"sb {_package_version()}"
    )
    subparsers = parser.add_subparsers(dest="command")
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
