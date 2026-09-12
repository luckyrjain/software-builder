#!/usr/bin/env python3
"""Entry point for the `sb` console script."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_version
from pathlib import Path

from sb._paths import registry_snapshot_root, vendored_scripts_root

sys.path.insert(0, str(vendored_scripts_root()))

from scripts.doctor import cmd_doctor  # noqa: E402
from scripts.registry.cli import cmd_compatibility, cmd_explain, cmd_list  # noqa: E402
from scripts.registry.compatibility_resolver import (  # noqa: E402
    UnknownHostError,
    available_capabilities,
    resolve_host,
)
from scripts.registry.host_registry import (  # noqa: E402
    HostRegistryParseError,
    parse_host_registry,
)
from scripts.registry.host_registry import (  # noqa: E402
    HostSpec,
    resolve_target_path,
)


def _package_version() -> str:
    try:
        return _installed_version("software-builder-cli")
    except PackageNotFoundError:
        return "unknown (not installed)"


def _default_install_roots_for_host(host: HostSpec, *, home: Path) -> list[Path]:
    """Same logic as scripts/doctor.py's own helper of the same name -- duplicated here
    rather than imported, since sb's argparse layer is a thin shim over the vendored
    library functions and this one piece of arg-resolution logic (turning --agent into a
    default --install-root list) lives in doctor.py's own main(), not in cmd_doctor itself,
    so there is no library function to call. Keep in sync with scripts/doctor.py's version
    if it changes."""
    roots: list[Path] = []
    seen: set[Path] = set()
    for surface in host.surfaces:
        for binding in surface.discovery:
            if binding.target.scope != "user":
                continue
            resolved = resolve_target_path(binding.target, home=home, target_dir=None)
            if resolved not in seen:
                seen.add(resolved)
                roots.append(resolved)
    return roots


def _cmd_doctor(args: argparse.Namespace) -> int:
    if args.agent is not None and args.available is not None:
        print("error: --agent and --available are mutually exclusive", file=sys.stderr)
        return 2

    root = registry_snapshot_root()
    host_id: str | None = None
    host_verification: str | None = None
    available: set[str] | None = None

    if args.agent is not None:
        try:
            host_registry = parse_host_registry(root / "agent-hosts.yaml")
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
        if args.surface is not None:
            declared_surfaces = {surface.kind for surface in host.surfaces}
            if args.surface not in declared_surfaces:
                print(
                    f"error: unknown surface {args.surface!r} for host {args.agent!r} "
                    f"(declared surfaces: {sorted(declared_surfaces)})",
                    file=sys.stderr,
                )
                return 2
        available = set(available_capabilities(host, args.surface))
    elif args.available is not None:
        available = {item.strip() for item in args.available.split(",") if item.strip()}

    install_roots = list(args.install_root)
    if not install_roots:
        if host_id is not None:
            install_roots = _default_install_roots_for_host(host, home=Path.home())
        else:
            install_roots = [Path.home() / ".cursor" / "skills"]

    return cmd_doctor(
        root,
        skill_filter=args.skill,
        available=available,
        install_roots=install_roots,
        host_id=host_id,
        host_verification=host_verification,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sb")
    parser.add_argument(
        "--version", action="version", version=f"sb {_package_version()}"
    )
    subparsers = parser.add_subparsers(dest="command")

    doctor_parser = subparsers.add_parser("doctor", help="check skill capability/install status")
    doctor_parser.add_argument("--skill", help="limit output to one skill id")
    doctor_parser.add_argument("--available", help="comma-separated capability names")
    doctor_parser.add_argument("--agent", help="host id or alias from agent-hosts.yaml")
    doctor_parser.add_argument(
        "--install-root", action="append", type=Path, default=[],
        help="installed skills directory (repeatable)",
    )
    doctor_parser.add_argument(
        "--surface",
        help="surface kind (e.g. LOCAL, CLOUD) from agent-hosts.yaml; narrows available "
        "capabilities to that surface's overrides where the host declares any",
    )

    subparsers.add_parser("list", help="list registered skills and their canonical metadata")

    explain_parser = subparsers.add_parser("explain", help="explain one skill's canonical metadata")
    explain_parser.add_argument("skill_id", help="registered skill identifier")

    compatibility_parser = subparsers.add_parser(
        "compatibility", help="resolve host x skill capability compatibility"
    )
    compatibility_parser.add_argument("--host", required=True, help="host id or alias from agent-hosts.yaml")
    compatibility_parser.add_argument("--skill", help="limit to one skill id")
    compatibility_parser.add_argument(
        "--surface",
        help="surface kind (e.g. LOCAL, CLOUD) from agent-hosts.yaml",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "doctor":
        return _cmd_doctor(args)
    if args.command == "list":
        return cmd_list(registry_snapshot_root())
    if args.command == "explain":
        return cmd_explain(registry_snapshot_root(), args.skill_id)
    if args.command == "compatibility":
        return cmd_compatibility(registry_snapshot_root(), args.host, args.skill, args.surface)

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
