#!/usr/bin/env python3
"""Ensure requirements.lock pins every package declared in requirements.txt."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIREMENT_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*>=")
LOCK_NAME_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==")
DIRECT_LOCK_MARKER = "# via -r requirements.txt"


def _normalize(name: str) -> str:
    # PEP 503: package name comparison is case-insensitive and treats runs of
    # -, _, . as equivalent (uv/pip canonicalize to '-' in requirements.lock).
    return re.sub(r"[-_.]+", "-", name.lower())


def package_names_from_requirements(path: Path) -> set[str]:
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = REQUIREMENT_NAME_RE.match(line)
        if not match:
            raise ValueError(f"unsupported requirements.txt entry: {line}")
        names.add(_normalize(match.group(1)))
    return names


def direct_package_names_from_lock(path: Path) -> set[str]:
    names: set[str] = set()
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        head = line.strip().rstrip("\\").strip()
        match = LOCK_NAME_RE.match(head)
        if match:
            current = _normalize(match.group(1))
        if DIRECT_LOCK_MARKER in line and current is not None:
            names.add(current)
    return names


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    requirements = repo_root / "requirements.txt"
    lockfile = repo_root / "requirements.lock"

    required = package_names_from_requirements(requirements)
    direct_locked = direct_package_names_from_lock(lockfile)

    missing = sorted(required - direct_locked)
    if missing:
        print(
            "error: requirements.lock is missing direct pinned entries for: "
            + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "hint: regenerate with "
            "`uv pip compile requirements.txt --generate-hashes "
            "--python-version 3.12 -o requirements.lock`",
            file=sys.stderr,
        )
        return 1

    extra = sorted(direct_locked - required)
    if extra:
        print(
            "error: requirements.lock has direct entries not declared in requirements.txt: "
            + ", ".join(extra),
            file=sys.stderr,
        )
        return 1

    print("ok: requirements.txt and direct requirements.lock entries match")
    return 0


if __name__ == "__main__":
    sys.exit(main())
