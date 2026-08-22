#!/usr/bin/env python3
"""Ensure requirements.lock pins every package declared in requirements.txt."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement
from packaging.version import InvalidVersion, Version

LOCK_ENTRY_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)")
DIRECT_LOCK_MARKER = "# via -r requirements.txt"


def _normalize(name: str) -> str:
    # PEP 503: package name comparison is case-insensitive and treats runs of
    # -, _, . as equivalent (uv/pip canonicalize to '-' in requirements.lock).
    return re.sub(r"[-_.]+", "-", name.lower())


def package_names_from_requirements(path: Path) -> set[str]:
    return set(requirements_from_file(path))


def requirements_from_file(path: Path) -> dict[str, Requirement]:
    requirements: dict[str, Requirement] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            requirement = Requirement(line)
        except InvalidRequirement as exc:
            raise ValueError(f"unsupported requirements.txt entry: {line}") from exc
        name = _normalize(requirement.name)
        if name in requirements:
            raise ValueError(f"duplicate requirements.txt entry: {requirement.name}")
        requirements[name] = requirement
    return requirements


def direct_locked_versions_from_lock(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    current: tuple[str, str] | None = None
    via_block = False
    for line in path.read_text(encoding="utf-8").splitlines():
        head = line.strip().rstrip("\\").strip()
        match = LOCK_ENTRY_RE.match(head)
        if match:
            current = (_normalize(match.group(1)), match.group(2))
            via_block = False
        if DIRECT_LOCK_MARKER in line and current is not None:
            name, version = current
            if name in versions and versions[name] != version:
                raise ValueError(f"duplicate direct lock entry: {name}")
            versions[name] = version
            current = None
            via_block = False
        elif current is not None and line.strip() == "# via":
            via_block = True
        elif via_block:
            if line.strip() == "#   -r requirements.txt" and current is not None:
                name, version = current
                if name in versions and versions[name] != version:
                    raise ValueError(f"duplicate direct lock entry: {name}")
                versions[name] = version
                current = None
            via_block = False
    return versions


def direct_package_names_from_lock(path: Path) -> set[str]:
    return set(direct_locked_versions_from_lock(path))


def unsatisfied_locked_requirements(
    requirements_path: Path, lockfile_path: Path
) -> list[str]:
    requirements = requirements_from_file(requirements_path)
    locked_versions = direct_locked_versions_from_lock(lockfile_path)
    errors: list[str] = []
    for name, requirement in sorted(requirements.items()):
        version_text = locked_versions.get(name)
        if version_text is None:
            continue
        try:
            version = Version(version_text)
        except InvalidVersion:
            errors.append(f"{name}=={version_text} is not a valid package version")
            continue
        if version not in requirement.specifier:
            errors.append(
                f"{name}=={version_text} does not satisfy {requirement}"
            )
    return errors


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

    unsatisfied = unsatisfied_locked_requirements(requirements, lockfile)
    if unsatisfied:
        print(
            "error: requirements.lock has pinned versions outside requirements.txt constraints:\n"
            + "\n".join(f"  - {entry}" for entry in unsatisfied),
            file=sys.stderr,
        )
        print(
            "hint: regenerate with "
            "`uv pip compile requirements.txt --generate-hashes "
            "--python-version 3.12 -o requirements.lock`",
            file=sys.stderr,
        )
        return 1

    print("ok: requirements.txt constraints and direct requirements.lock entries match")
    return 0


if __name__ == "__main__":
    sys.exit(main())

