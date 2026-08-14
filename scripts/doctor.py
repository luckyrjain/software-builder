#!/usr/bin/env python3
"""Preflight / doctor command for software-builder skills."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reference_utils import ManifestError, MANIFEST_NAME, read_manifest_file
from scripts.registry.models import CapabilityPath, SkillEntry
from scripts.registry.schema import parse_registry
from scripts.yaml_safety import YAML_SAFETY_ERRORS
from scripts.release_info import read_distribution_version


def _installed_manifest(skill_dest: Path) -> dict[str, object] | None:
    try:
        return read_manifest_file(skill_dest / MANIFEST_NAME)
    except ManifestError:
        # A missing or corrupt manifest just means "can't determine install
        # status" for this skill -- not a doctor-run failure.
        return None


def _capability_status(
    entry_required: list[str],
    entry_optional: list[str],
    entry_any_of: list[CapabilityPath],
    available: set[str] | None,
) -> tuple[list[str], list[str], str, CapabilityPath | None]:
    if available is None:
        return [], [], "UNSPECIFIED", None
    missing_required = [cap for cap in entry_required if cap not in available]
    if missing_required:
        return missing_required, [], "BLOCKED", None

    active_path: CapabilityPath | None = None
    if entry_any_of:
        complete_paths = [
            path for path in entry_any_of if all(cap in available for cap in path.required)
        ]
        if not complete_paths:
            closest_path = min(
                entry_any_of,
                key=lambda path: sum(cap not in available for cap in path.required),
            )
            missing_required = [cap for cap in closest_path.required if cap not in available]
            return missing_required, [], "BLOCKED", None
        active_path = min(
            complete_paths,
            key=lambda path: sum(item.name not in available for item in path.optional),
        )

    active_optional = list(entry_optional)
    if active_path is not None:
        active_optional.extend(item.name for item in active_path.optional)
    missing_optional = [cap for cap in active_optional if cap not in available]
    if missing_optional:
        return missing_required, missing_optional, "DEGRADED", active_path
    return missing_required, missing_optional, "READY", active_path


@dataclass(frozen=True)
class SkillStatus:
    """A skill's computed doctor status, independent of how it gets rendered."""

    skill_id: str
    entry: SkillEntry
    status: str
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    installed_label: str = "not installed"
    active_path: CapabilityPath | None = None
    available: frozenset[str] | None = None


def _skill_status(
    skill_id: str,
    entry: SkillEntry,
    *,
    available: set[str] | None,
    install_roots: list[Path],
    distribution_version: str,
) -> SkillStatus:
    optional_names = [item.name for item in entry.capabilities.optional]
    missing_required, missing_optional, status, active_path = _capability_status(
        entry.capabilities.required,
        optional_names,
        entry.capabilities.any_of,
        available,
    )

    installed_label = "not installed"
    for install_root in install_roots:
        dest = install_root / skill_id
        manifest = _installed_manifest(dest)
        if manifest is None:
            continue
        installed_version = manifest.get("distribution_version")
        installed_version = installed_version if isinstance(installed_version, str) else "unknown"
        installed_sha = manifest.get("source_sha")
        installed_sha = installed_sha if isinstance(installed_sha, str) else "unknown"
        installed_label = f"installed ({installed_version} @ {installed_sha[:12]})"
        if installed_version != distribution_version:
            status = "VERSION_MISMATCH"
        break

    return SkillStatus(
        skill_id=skill_id,
        entry=entry,
        status=status,
        missing_required=missing_required,
        missing_optional=missing_optional,
        installed_label=installed_label,
        active_path=active_path,
        available=frozenset(available) if available is not None else None,
    )


def render_skill_status(status: SkillStatus) -> str:
    entry = status.entry
    lines = [f"\n{status.skill_id}: {status.status}"]
    lines.append(f"  invocation: {entry.invocation}")
    lines.append(f"  composition.mode: {entry.composition.mode}")
    if entry.composition.invokes:
        lines.append(f"  invokes: {', '.join(entry.composition.invokes)}")
    if entry.capabilities.required:
        lines.append(f"  required capabilities: {', '.join(entry.capabilities.required)}")
    if entry.capabilities.any_of:
        lines.append("  any-of capability paths:")
        for path in entry.capabilities.any_of:
            if status.available is None:
                path_status = "not evaluated"
            else:
                path_missing = [cap for cap in path.required if cap not in status.available]
                path_status = (
                    "ready" if not path_missing else f"missing {', '.join(path_missing)}"
                )
            lines.append(f"    {path.name}: {', '.join(path.required)} ({path_status})")
    active_optional = list(entry.capabilities.optional)
    if status.active_path is not None:
        lines.append(f"  selected capability path: {status.active_path.name}")
        active_optional.extend(status.active_path.optional)
    if active_optional:
        labels = [
            f"{item.name} ({item.enables})" if item.enables else item.name
            for item in active_optional
        ]
        lines.append(f"  optional capabilities: {', '.join(labels)}")
    if status.missing_required:
        lines.append(f"  missing required: {', '.join(status.missing_required)}")
        for cap in status.missing_required:
            degraded = entry.capabilities.degraded_modes.get(cap)
            if degraded:
                lines.append(f"    {cap} -> {degraded}")
    if status.missing_optional:
        lines.append(f"  missing optional: {', '.join(status.missing_optional)}")
        for cap in status.missing_optional:
            degraded = entry.capabilities.degraded_modes.get(cap)
            if degraded:
                lines.append(f"    {cap} -> {degraded}")
    lines.append(f"  install: {status.installed_label}")
    if status.status == "UNSPECIFIED" and (
        entry.capabilities.required
        or entry.capabilities.optional
        or entry.capabilities.any_of
    ):
        lines.append("  capability check: pass --available to evaluate host capabilities")
    return "\n".join(lines)


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

        status = _skill_status(
            skill_id,
            entry,
            available=available,
            install_roots=install_roots,
            distribution_version=distribution_version,
        )
        print(render_skill_status(status))

        if status.status in {"BLOCKED", "VERSION_MISMATCH"}:
            exit_code = 1

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
    except YAML_SAFETY_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
