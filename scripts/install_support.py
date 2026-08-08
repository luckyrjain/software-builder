#!/usr/bin/env python3
"""Helpers for scripts/install.sh: registry allowlist and installed-package verify."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_NAME = ".software-builder-manifest.json"


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


def cmd_verify(installed_path: Path) -> int:
    if not installed_path.is_dir():
        print(f"error: not a directory: {installed_path}", file=sys.stderr)
        return 1
    manifest_path = installed_path / MANIFEST_NAME
    if not manifest_path.is_file():
        print(f"error: missing manifest: {manifest_path}", file=sys.stderr)
        return 1
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"error: invalid manifest JSON: {exc}", file=sys.stderr)
        return 1
    skill_name = manifest.get("skill")
    if not isinstance(skill_name, str) or not skill_name:
        print("error: manifest missing skill name", file=sys.stderr)
        return 1

    from scripts.validate_references import validate_tree

    errors = validate_tree(installed_path, check_anchors=False, installed_package=True)
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

    args = parser.parse_args(argv)
    if args.command == "list":
        return cmd_list(args.repo_root)
    if args.command == "check":
        return cmd_check(args.skill_id, args.repo_root)
    if args.command == "verify":
        return cmd_verify(args.installed_path)

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
