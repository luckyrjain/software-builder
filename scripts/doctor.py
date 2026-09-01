#!/usr/bin/env python3
"""Preflight / doctor command for software-builder skills."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.reference_utils import ManifestError, MANIFEST_NAME, read_manifest_file
from scripts.registry.capability_engine import capability_status as _capability_status
from scripts.registry.compatibility_resolver import (
    UnknownHostError,
    available_capabilities,
    resolve_host,
)
from scripts.registry.host_registry import HostRegistryParseError, parse_host_registry
from scripts.registry.models import CapabilityPath, SkillEntry
from scripts.registry.schema import parse_registry
from scripts.yaml_safety import YAML_SAFETY_ERRORS
from scripts.release_info import read_distribution_version

# Combined with a skill's own capability_status by _apply_host_verification below (spec Section
# 10/26): a host that hasn't earned VERIFIED status can't make a READY/DEGRADED claim credible.
# Named per Section 41's doctor status vocabulary (UNVERIFIED_HOST/CONFLICTED_HOST_EVIDENCE), not
# scripts/registry/compatibility_resolver.py's bare UNVERIFIED/CONFLICTED -- doctor's own status
# space has other reasons a skill can be unverified (VERSION_MISMATCH, etc.), so the host-specific
# ones need their own names to stay unambiguous in rendered output.
_HOST_VERIFICATION_STATUS = {
    "UNVERIFIED": "UNVERIFIED_HOST",
    "CONFLICTED": "CONFLICTED_HOST_EVIDENCE",
}


def _installed_manifest(skill_dest: Path) -> dict[str, object] | None:
    try:
        return read_manifest_file(skill_dest / MANIFEST_NAME)
    except ManifestError:
        # A missing or corrupt manifest just means "can't determine install
        # status" for this skill -- not a doctor-run failure.
        return None


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
    host_id: str | None = None
    host_verification: str | None = None
    capability_status: str | None = None


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
    capability_status = status

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
        capability_status=capability_status,
    )


def _apply_host_verification(status: SkillStatus, *, host_id: str, host_verification: str) -> SkillStatus:
    """Downgrade a READY/DEGRADED capability result per the host's own verification state (spec
    Section 10/26), matching scripts/registry/compatibility_resolver.py's combine logic exactly --
    reused conceptually rather than by direct call, since doctor.py already computed
    capability_status/missing_required/etc. via its own `_capability_status` engine (the one
    compatibility_resolver.py itself reuses) and VERSION_MISMATCH is a doctor-only precedence tier
    that engine doesn't know about.

    BLOCKED and VERSION_MISMATCH are already the most informative signal available and are left
    untouched; only a would-be READY/DEGRADED claim is downgraded, and only for a host that hasn't
    earned VERIFIED status. See _HOST_VERIFICATION_STATUS for why the displayed name differs from
    compatibility_resolver.py's bare UNVERIFIED/CONFLICTED.
    """
    display_status = status.status
    if status.status in {"READY", "DEGRADED"}:
        override = _HOST_VERIFICATION_STATUS.get(host_verification)
        if override is not None:
            display_status = override
    return replace(status, status=display_status, host_id=host_id, host_verification=host_verification)


def render_skill_status(status: SkillStatus) -> str:
    entry = status.entry
    lines = [f"\n{status.skill_id}: {status.status}"]
    if status.host_id is not None:
        lines.append(f"  host: {status.host_id} (verification: {status.host_verification})")
        if status.status != status.capability_status:
            lines.append(f"  capability result: {status.capability_status} (host not yet verified)")
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
    host_id: str | None = None,
    host_verification: str | None = None,
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
        if host_id is not None:
            status = _apply_host_verification(status, host_id=host_id, host_verification=host_verification)
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
        help="comma-separated capability names present in the host environment "
        "(mutually exclusive with --agent, which derives this from agent-hosts.yaml)",
    )
    parser.add_argument(
        "--agent",
        help="host id or alias from agent-hosts.yaml; derives available capabilities and "
        "verification state from the registry instead of --available (Candidate 10)",
    )
    parser.add_argument(
        "--surface",
        help="informational only for now: agent-hosts.yaml's HostSpec.capabilities is not yet "
        "nested per surface (see scripts/registry/compatibility_resolver.py), so this does not "
        "yet change which capabilities are considered available",
    )
    parser.add_argument(
        "--install-root",
        action="append",
        type=Path,
        default=[],
        help="installed skills directory (repeatable; defaults to ~/.cursor/skills)",
    )
    args = parser.parse_args(argv)

    if args.agent is not None and args.available is not None:
        print("error: --agent and --available are mutually exclusive", file=sys.stderr)
        return 2

    host_id: str | None = None
    host_verification: str | None = None
    available: set[str] | None = None
    if args.agent is not None:
        try:
            host_registry = parse_host_registry(args.repo_root / "agent-hosts.yaml")
        except HostRegistryParseError as exc:
            for error in exc.errors:
                print(f"error: {error}", file=sys.stderr)
            return 2
        try:
            host = resolve_host(host_registry, args.agent)
        except UnknownHostError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        host_id = args.agent
        host_verification = host.verification
        available = set(available_capabilities(host))
        if args.surface is not None:
            print(
                f"note: --surface {args.surface!r} does not yet affect capability resolution "
                "(agent-hosts.yaml capabilities are host-level, not per-surface)",
                file=sys.stderr,
            )
    elif args.available is not None:
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
            host_id=host_id,
            host_verification=host_verification,
        )
    except YAML_SAFETY_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
