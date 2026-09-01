#!/usr/bin/env python3
"""Helpers for scripts/install.sh: registry allowlist and installed-package verify."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scripts.reference_utils import (
    MANIFEST_NAME,
    ManifestError,
    classify_install_destination,
    is_ignored_package_path,
    read_manifest_file,
    sha256_file,
)
from scripts.registry.host_registry import HostRegistryParseError, parse_host_registry
from scripts.registry.legacy_install_resolver import resolve_legacy_install_destinations
from scripts.registry.shadow_detector import HOST_LABEL_TO_HOST_AND_TARGET, SHADOW_NONE, detect_shadow
from scripts.registry.universal_install_resolver import (
    UNIVERSAL_AGENT_SELECTOR,
    resolve_universal_install_destination,
)
from scripts.registry.schema import parse_registry
from scripts.yaml_safety import YAML_SAFETY_ERRORS

ROOT = Path(__file__).resolve().parents[1]


def registry_skill_ids(root: Path | None = None) -> list[str]:
    repo_root = root or ROOT
    registry = parse_registry(repo_root / "skills.yaml")
    return sorted(registry.skills.keys())


def cmd_list(root: Path) -> int:
    for skill_id in registry_skill_ids(root):
        print(skill_id)
    return 0


def cmd_check(skill_id: str, root: Path) -> int:
    if skill_id not in set(registry_skill_ids(root)):
        print(f"error: {skill_id!r} is not in skills.yaml", file=sys.stderr)
        return 1
    return 0


def _verify_manifest_files(installed_path: Path, manifest: dict) -> list[str]:
    """Compare the installed directory's files against the manifest's files
    (path -> sha256) map written by package_skill.py. Reports missing files,
    hash mismatches, and files present on disk but not tracked in the manifest
    -- the installed directory should be byte-identical to what was packaged,
    since install.sh moves the staged package into place with no further writes.

    Filesystem noise that can legitimately appear after install (running a
    bundled script writes __pycache__, editors/OS write dotfiles) is excluded
    via the same is_ignored_package_path() package_skill.py's own copytree
    ignore list is built from, so a normal post-install workflow doesn't fail
    verification. A symlink anywhere under installed_path is flagged directly
    rather than followed -- cmd_verify validates untrusted-ish installed
    content, and hashing through a symlink would read whatever it points at,
    including a path outside installed_path entirely. Anything that's neither
    a regular file, a directory, nor a symlink (a FIFO, socket, or device
    node) is flagged the same way -- the installed directory should contain
    nothing but what package_skill.py wrote.
    """
    files = manifest.get("files")
    if not isinstance(files, dict):
        return ["manifest missing files map"]

    errors: list[str] = []
    actual: set[str] = set()
    symlinks: set[str] = set()
    other_entries: set[str] = set()
    for path in installed_path.rglob("*"):
        rel = path.relative_to(installed_path).as_posix()
        if path.is_symlink():
            symlinks.add(rel)
            continue
        if path.is_dir():
            continue
        if not path.is_file():
            other_entries.add(rel)
            continue
        if path.name == MANIFEST_NAME or is_ignored_package_path(rel):
            continue
        actual.add(rel)

    unusable = symlinks | other_entries
    for rel in sorted(symlinks):
        errors.append(f"symlink not allowed in installed package: {rel}")
    for rel in sorted(other_entries):
        errors.append(f"unexpected filesystem entry (not a regular file): {rel}")

    for rel, expected_hash in sorted(files.items()):
        if rel in unusable:
            continue
        if rel not in actual:
            errors.append(f"missing file listed in manifest: {rel}")
            continue
        try:
            actual_hash = sha256_file(installed_path / rel)
        except OSError as exc:
            errors.append(f"could not read {rel} to verify its hash: {exc}")
            continue
        if actual_hash != expected_hash:
            errors.append(f"hash mismatch for {rel}: expected {expected_hash}, got {actual_hash}")

    for rel in sorted(actual - files.keys()):
        errors.append(f"unexpected file not in manifest: {rel}")

    return errors


def cmd_classify_destination(dest: Path, skill_id: str) -> int:
    """Print one of ABSENT/SOFTWARE_BUILDER_OWNED/UNOWNED/CORRUPT_OWNERSHIP/SYMLINK for install.sh's
    ownership-hardened install_skill()/uninstall_skill() to branch on (Candidate 6)."""
    print(classify_install_destination(dest, skill_id=skill_id))
    return 0


def cmd_resolve_targets(root: Path, agent: str, *, home: Path, target_dir: Path | None) -> int:
    """Print `<dest_root>\\t<host_label>` per line for install.sh's dest_roots()/
    host_label_for_dest() to consume, resolved from agent-hosts.yaml instead of Bash's own
    hard-coded case statements (Candidate 5), plus the universal `agents` selector (Candidate 7)."""
    try:
        host_registry = parse_host_registry(root / "agent-hosts.yaml")
    except HostRegistryParseError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    try:
        if agent == UNIVERSAL_AGENT_SELECTOR:
            destinations = [
                resolve_universal_install_destination(host_registry, home=home, target_dir=target_dir)
            ]
        else:
            destinations = resolve_legacy_install_destinations(
                host_registry, agent, home=home, target_dir=target_dir
            )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    for dest_root, host_label in destinations:
        print(f"{dest_root}\t{host_label}")
    return 0


def cmd_check_shadow(
    root: Path, host_label: str, written_dest: Path, *, home: Path, target_dir: Path | None
) -> int:
    """Print NONE/SHADOWED/DUPLICATE_IDENTICAL/UNKNOWN_PRECEDENCE (and, on the second line, the
    shadowing path if not NONE) for install.sh to build an accurate completion message from
    instead of unconditionally claiming the new install is what the host will run (Candidate 8).
    """
    host_and_target = HOST_LABEL_TO_HOST_AND_TARGET.get(host_label)
    if host_and_target is None:
        # No host entry to check against (e.g. the universal agents-user/agents-project
        # labels) -- see shadow_detector.py's module docstring for why this is a scoped gap,
        # not a bug.
        print(SHADOW_NONE)
        return 0
    host_id, target_id = host_and_target
    try:
        host_registry = parse_host_registry(root / "agent-hosts.yaml")
    except HostRegistryParseError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    result = detect_shadow(
        host_registry, host_id, target_id, written_dest, home=home, target_dir=target_dir
    )
    print(result.status)
    if result.shadowing_path is not None:
        print(result.shadowing_path)
    return 0


def cmd_verify(installed_path: Path) -> int:
    if not installed_path.is_dir():
        print(f"error: not a directory: {installed_path}", file=sys.stderr)
        return 1
    try:
        manifest = read_manifest_file(installed_path / MANIFEST_NAME)
    except ManifestError as exc:
        # Unlike doctor.py's status check, a broken manifest IS the failure
        # this command reports -- surface it, don't degrade silently.
        print(f"error: {exc}", file=sys.stderr)
        return 1
    skill_name = manifest.get("skill")
    if not isinstance(skill_name, str) or not skill_name:
        print("error: manifest missing skill name", file=sys.stderr)
        return 1

    from scripts.validate_references import validate_tree

    errors = validate_tree(installed_path, check_anchors=False, installed_package=True)
    errors.extend(_verify_manifest_files(installed_path, manifest))
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"ok: {installed_path} ({skill_name})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="install_support")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="print registry skill ids")
    list_parser.add_argument("--repo-root", type=Path, default=ROOT)

    check_parser = sub.add_parser("check", help="verify skill id is in registry")
    check_parser.add_argument("skill_id")
    check_parser.add_argument("--repo-root", type=Path, default=ROOT)

    verify_parser = sub.add_parser("verify", help="verify an installed skill package")
    verify_parser.add_argument("installed_path", type=Path)

    resolve_parser = sub.add_parser(
        "resolve-targets", help="resolve a legacy --agent selector's install destinations"
    )
    resolve_parser.add_argument("agent")
    resolve_parser.add_argument("--repo-root", type=Path, default=ROOT)
    resolve_parser.add_argument("--home", type=Path, default=Path.home())
    resolve_parser.add_argument("--target-dir", type=Path, default=None)

    classify_parser = sub.add_parser(
        "classify-destination", help="classify an install destination's ownership state"
    )
    classify_parser.add_argument("dest", type=Path)
    classify_parser.add_argument("skill_id")

    shadow_parser = sub.add_parser(
        "check-shadow", help="check whether an install is shadowed by a higher-precedence root"
    )
    shadow_parser.add_argument("host_label")
    shadow_parser.add_argument("written_dest", type=Path)
    shadow_parser.add_argument("--repo-root", type=Path, default=ROOT)
    shadow_parser.add_argument("--home", type=Path, default=Path.home())
    shadow_parser.add_argument("--target-dir", type=Path, default=None)

    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            return cmd_list(args.repo_root)
        if args.command == "check":
            return cmd_check(args.skill_id, args.repo_root)
        if args.command == "verify":
            return cmd_verify(args.installed_path)
        if args.command == "resolve-targets":
            return cmd_resolve_targets(
                args.repo_root, args.agent, home=args.home, target_dir=args.target_dir
            )
        if args.command == "classify-destination":
            return cmd_classify_destination(args.dest, args.skill_id)
        if args.command == "check-shadow":
            return cmd_check_shadow(
                args.repo_root,
                args.host_label,
                args.written_dest,
                home=args.home,
                target_dir=args.target_dir,
            )
    except YAML_SAFETY_ERRORS as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
