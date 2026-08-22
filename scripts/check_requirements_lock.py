#!/usr/bin/env python3
"""Ensure requirements.lock pins every package declared in requirements.txt."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement

LOCK_ENTRY_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s\\]+)$")
DIRECT_LOCK_MARKER = "# via -r requirements.txt"
LOCK_TARGET_ENVIRONMENT = {
    **default_environment(),
    "implementation_name": "cpython",
    "implementation_version": "3.12.0",
    "os_name": "posix",
    "platform_machine": "x86_64",
    "platform_python_implementation": "CPython",
    "platform_release": "",
    "platform_system": "Linux",
    "platform_version": "",
    "python_version": "3.12",
    "python_full_version": "3.12.0",
    "sys_platform": "linux",
}


def _normalize(name: str) -> str:
    # PEP 503: package name comparison is case-insensitive and treats runs of
    # -, _, . as equivalent (uv/pip canonicalize to '-' in requirements.lock).
    return re.sub(r"[-_.]+", "-", name.lower())


def package_names_from_requirements(path: Path) -> set[str]:
    return set(requirements_from_file(path))


def requirements_from_file(path: Path) -> dict[str, list[Requirement]]:
    requirements: dict[str, list[Requirement]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = re.split(r"\s+#", line, maxsplit=1)[0].strip()
        if not line or line.startswith("#"):
            continue
        try:
            requirement = Requirement(line)
        except InvalidRequirement as exc:
            raise ValueError(f"unsupported requirements.txt entry: {line}") from exc
        if requirement.marker is not None and not requirement.marker.evaluate(
            LOCK_TARGET_ENVIRONMENT
        ):
            continue
        name = _normalize(requirement.name)
        requirements.setdefault(name, []).append(requirement)
    return requirements


def direct_locked_versions_from_lock(path: Path) -> dict[str, str]:
    versions: dict[str, str] = {}
    current: tuple[str, str] | None = None
    via_block = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        head = line.strip().rstrip("\\").strip()
        match = LOCK_ENTRY_RE.match(head)
        if match:
            current = (_normalize(match.group(1)), match.group(2))
            via_block = False
            continue
        if current is None:
            continue
        if stripped.startswith("--hash="):
            continue
        if stripped == DIRECT_LOCK_MARKER:
            name, version = current
            if name in versions:
                raise ValueError(f"duplicate direct lock entry: {name}")
            versions[name] = version
            current = None
            via_block = False
        elif stripped == "# via":
            via_block = True
        elif via_block:
            if stripped == "#   -r requirements.txt":
                name, version = current
                if name in versions:
                    raise ValueError(f"duplicate direct lock entry: {name}")
                versions[name] = version
                current = None
                via_block = False
            elif not stripped.startswith("#   "):
                current = None
                via_block = False
        else:
            current = None
    return versions


def direct_package_names_from_lock(path: Path) -> set[str]:
    return set(direct_locked_versions_from_lock(path))


def unsatisfied_locked_requirements(
    requirements_path: Path, lockfile_path: Path
) -> list[str]:
    requirements = requirements_from_file(requirements_path)
    locked_versions = direct_locked_versions_from_lock(lockfile_path)
    errors: list[str] = []
    for name, requirement_group in sorted(requirements.items()):
        version_text = locked_versions.get(name)
        if version_text is None:
            continue
        for requirement in requirement_group:
            if not requirement.specifier.contains(version_text):
                errors.append(
                    f"{name}=={version_text} does not satisfy {requirement}"
                )
    return errors


def _main_impl() -> int:
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


def main() -> int:
    try:
        return _main_impl()
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

