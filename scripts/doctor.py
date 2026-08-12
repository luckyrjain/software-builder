#!/usr/bin/env python3
"""Preflight / doctor command for software-builder skills."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reference_utils import MANIFEST_NAME
from scripts.registry.schema import parse_registry
from scripts.release_info import read_distribution_version


def _installed_manifest(skill_dest: Path) -> dict[str, object] | None:
    manifest_path = skill_dest / MANIFEST_NAME
    if not manifest_path.is_file():
        return None
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _capability_status(
    entry_required: list[str],
    entry_optional: list[str],
    available: set[str] | None,
) -> tuple[list[str], list[str], str]:
    if available is None:
        return [], [], "UNSPECIFIED"
    missing_required = [cap for cap in entry_required if cap not in available]
    missing_optional = [cap for cap in entry_optional if cap not in available]
    if missing_required:
        return missing_required, missing_optional, "BLOCKED"
    if missing_optional:
        return missing_required, missing_optional, "DEGRADED"
    if entry_required or entry_optional:
        return missing_required, missing_optional, "READY"
    return missing_required, missing_optional, "READY"


def cmd_doctor(
    root: Path,
    *,
    skill_filter: str | None,
    available: set[str] | None,
    install_roots: list[Path],
) -> int:
    registry = parse_registry(root / "skills.yaml")
    distribution_version = read_distribution_version(root)
    exit_code = 0

    print(f"software-builder doctor (distribution {distribution_version})")
    for skill_id, entry in sorted(registry.skills.items()):
        if skill_filter and skill_id != skill_filter:
            continue

        optional_names = [item.name for item in entry.capabilities.optional]
        missing_required, missing_optional, status = _capability_status(
            entry.capabilities.required,
            optional_names,
            available,
        )

        installed_label = "not installed"
        for install_root in install_roots:
            dest = install_root / skill_id
            manifest = _installed_manifest(dest)
            if manifest is None:
                continue
            installed_version = manifest.get("distribution_version", "unknown")
            installed_sha = manifest.get("source_sha", "unknown")
            installed_label = f"installed ({installed_version} @ {installed_sha[:12]})"
            if installed_version != distribution_version:
                status = "VERSION_MISMATCH"
            break

        print(f"\n{skill_id}: {status}")
        print(f"  invocation: {entry.invocation}")
        print(f"  composition.mode: {entry.composition.mode}")
        if entry.composition.invokes:
            print(f"  invokes: {', '.join(entry.composition.invokes)}")
        if entry.capabilities.required:
            print(f"  required capabilities: {', '.join(entry.capabilities.required)}")
        if entry.capabilities.optional:
            labels = [
                f"{item.name} ({item.enables})" if item.enables else item.name
                for item in entry.capabilities.optional
            ]
            print(f"  optional capabilities: {', '.join(labels)}")
        if missing_required:
            print(f"  missing required: {', '.join(missing_required)}")
            for cap in missing_required:
                degraded = entry.capabilities.degraded_modes.get(cap)
                if degraded:
                    print(f"    {cap} -> {degraded}")
        if missing_optional:
            print(f"  missing optional: {', '.join(missing_optional)}")
            for cap in missing_optional:
                degraded = entry.capabilities.degraded_modes.get(cap)
                if degraded:
                    print(f"    {cap} -> {degraded}")
        print(f"  install: {installed_label}")

        if status in {"BLOCKED", "VERSION_MISMATCH"}:
            exit_code = 1
        if status == "UNSPECIFIED" and (entry.capabilities.required or entry.capabilities.optional):
            print("  capability check: pass --available to evaluate host capabilities")

    return exit_code


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="doctor")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--skill", help="limit output to one skill id")
    parser.add_argument(
        "--available",
        help="comma-separated capability names present in the host environment",
    )
    parser.add_argument(
        "--install-root",
        action="append",
        type=Path,
        default=[],
        help="installed skills directory (repeatable; defaults to ~/.cursor/skills)",
    )
    args = parser.parse_args(argv)

    available: set[str] | None = None
    if args.available is not None:
        available = {item.strip() for item in args.available.split(",") if item.strip()}

    install_roots = list(args.install_root)
    if not install_roots:
        install_roots = [Path.home() / ".cursor" / "skills"]

    try:
        return cmd_doctor(
            args.repo_root,
            skill_filter=args.skill,
            available=available,
            install_roots=install_roots,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
