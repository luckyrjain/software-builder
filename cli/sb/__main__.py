#!/usr/bin/env python3
"""Entry point for the `sb` console script."""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _installed_version
from pathlib import Path
from typing import Any, Callable

from sb._paths import registry_snapshot_root, vendored_scripts_root

sys.path.insert(0, str(vendored_scripts_root()))

from scripts.doctor import cmd_doctor_resolved  # noqa: E402
from scripts.registry.cli import cmd_compatibility, cmd_explain, cmd_list  # noqa: E402
from scripts.registry.host_registry import HostRegistry, parse_host_registry  # noqa: E402
from scripts.install_engine import _sigterm_as_system_exit, install_skill, uninstall_skill  # noqa: E402
from scripts.install_support import cmd_verify  # noqa: E402
from scripts.registry.install_resolver import (  # noqa: E402
    host_and_target_for_label,
    install_selectors,
    resolve_install_destinations,
)
from scripts.registry.shadow_detector import detect_shadow, render_shadow_warning  # noqa: E402
from sb._update import run_update  # noqa: E402


def _package_version() -> str:
    try:
        return _installed_version("software-builder-cli")
    except PackageNotFoundError:
        return "unknown (not installed)"


def _cmd_doctor(args: argparse.Namespace) -> int:
    return cmd_doctor_resolved(
        registry_snapshot_root(),
        skill=args.skill,
        available=args.available,
        agent=args.agent,
        surface=args.surface,
        install_root=args.install_root,
    )


def _resolve_destinations(agent: str, target_dir: Path | None) -> tuple[HostRegistry, list[tuple[Path, str]]]:
    host_registry = parse_host_registry(registry_snapshot_root() / "agent-hosts.yaml")
    destinations = resolve_install_destinations(host_registry, agent, home=Path.home(), target_dir=target_dir)
    return host_registry, destinations


def _warn_if_shadowed(
    host_registry: HostRegistry, host_label: str, skill_dest: Path, *, target_dir: Path | None
) -> None:
    """Mirror install.sh's post-install shadow check (Candidate 8): a divergent copy at a
    higher-precedence discovery root for this host means the host will actually load THAT copy,
    not the one just written here, so the completion message must say so. This is a report, not a
    refusal -- the install this decorates already succeeded and stands regardless of what this
    finds.

    Broad except, matching install.sh's own guard: this runs after the install already succeeded,
    so a failure here (e.g. an unexpected exception inside detect_shadow) must not read as the
    install itself having failed -- it's downgraded to an unknown-shadow-status warning instead.
    """
    host_and_target = host_and_target_for_label(host_registry, host_label)
    if host_and_target is None:
        return
    host_id, target_id = host_and_target
    try:
        result = detect_shadow(
            host_registry, host_id, target_id, skill_dest, home=Path.home(), target_dir=target_dir
        )
    except Exception:
        print(f"warning: could not determine shadow status for {skill_dest}", file=sys.stderr)
        return
    message = render_shadow_warning(result, host_label)
    if message is not None:
        print(message, file=sys.stderr)


def _run_batch(
    skill_ids: list[str],
    destinations: list[tuple[Path, str]],
    operation: Callable[[str, Path, str], Any],
    *,
    dry_run: bool,
    verb: str,
    past_tense: str,
    success_status: str,
    extra_ok_statuses: frozenset[str] = frozenset(),
    on_success: Callable[[str, Any], None] | None = None,
) -> int:
    """Runs `operation` over every (skill_id, destination) pair, tallies outcomes by status,
    and prints a summary when there's more than one pair -- the resolve/loop/tally/summarize
    shape `_cmd_install`/`_cmd_uninstall` used to each reimplement independently, differing
    only in the engine call, the success-status label, and install's extra shadow-warning
    hook (now `on_success`).
    """
    succeeded = failed = dry_run_count = 0
    try:
        # The engine converts a terminate signal only while it is doing the work of one
        # install; between skills (and while printing) it would kill the process with the raw
        # 143 instead of the clean stop `sb` promises. SIGINT already arrives as
        # KeyboardInterrupt.
        with _sigterm_as_system_exit():
            for skill_id in skill_ids:
                for dest_root, host_label in destinations:
                    outcome = operation(skill_id, dest_root, host_label)
                    print(outcome.message)
                    if outcome.status == "failed":
                        failed += 1
                    elif outcome.status == success_status:
                        succeeded += 1
                        if on_success is not None:
                            on_success(host_label, outcome)
                    elif outcome.status == "dry_run":
                        dry_run_count += 1
                    elif outcome.status not in extra_ok_statuses:
                        # Fail loud, not silently-undercount: install_engine.py's own CLI presentation
                        # (_PRESENTATION) enumerates the same status values independently -- a status
                        # added there without a matching branch here must not pass silently.
                        raise AssertionError(f"unhandled {verb} outcome status: {outcome.status!r}")
    except (KeyboardInterrupt, SystemExit):
        # The engine has already rolled back the interrupted skill; report what did finish
        # rather than a traceback, and exit 130 so a wrapper treats it as a whole-run stop.
        print(f"interrupted: {succeeded} completed, {failed} failed", file=sys.stderr)
        return 130
    if len(skill_ids) * len(destinations) > 1:
        if dry_run:
            print(f"would {verb}: {dry_run_count}, failed: {failed}", file=sys.stderr)
        else:
            print(f"{past_tense}: {succeeded}, failed: {failed}", file=sys.stderr)
    return 1 if failed else 0


def _cmd_install(args: argparse.Namespace) -> int:
    try:
        host_registry, destinations = _resolve_destinations(args.host, args.target_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    def _install_one(skill_id: str, dest_root: Path, host_label: str) -> Any:
        return install_skill(
            skill_id,
            repo_root=registry_snapshot_root(),
            dest_root=dest_root,
            host_label=host_label,
            dry_run=args.dry_run,
        )

    def _on_installed(host_label: str, outcome: Any) -> None:
        _warn_if_shadowed(host_registry, host_label, outcome.dest, target_dir=args.target_dir)

    return _run_batch(
        args.skill_ids,
        destinations,
        _install_one,
        dry_run=args.dry_run,
        verb="install",
        past_tense="installed",
        success_status="installed",
        on_success=_on_installed,
    )


def _cmd_uninstall(args: argparse.Namespace) -> int:
    try:
        _host_registry, destinations = _resolve_destinations(args.host, args.target_dir)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    def _uninstall_one(skill_id: str, dest_root: Path, _host_label: str) -> Any:
        return uninstall_skill(skill_id, dest_root=dest_root, dry_run=args.dry_run)

    return _run_batch(
        args.skill_ids,
        destinations,
        _uninstall_one,
        dry_run=args.dry_run,
        verb="uninstall",
        past_tense="uninstalled",
        success_status="uninstalled",
        extra_ok_statuses=frozenset({"absent"}),
    )


def main(argv: list[str] | None = None) -> int:
    # install_skill()/uninstall_skill() outcome messages contain a non-ASCII arrow (U+2192,
    # matching install.sh's own historical text byte-for-byte); Python's print() is
    # locale-aware and can raise UnicodeEncodeError under a restrictive locale (LC_ALL=C),
    # crashing after a successful install and getting it reported as failed.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

    install_parser = subparsers.add_parser(
        "install",
        help="install one or more skills",
        description=(
            "Install one or more skills. Warns, like install.sh, when a higher-precedence "
            "discovery root for this host already carries a divergent copy. Does not run "
            "agent-hosts.yaml's registry-wide selector-coverage validation -- a repo-health "
            "lint, not something install.sh itself runs per install either."
        ),
    )
    install_parser.add_argument("skill_ids", nargs="+", help="registered skill id(s)")
    install_parser.add_argument("--host", required=True, help=f"install selector: {', '.join(install_selectors())}")
    install_parser.add_argument("--target-dir", type=Path, default=None, help="project root for project-scope targets")
    install_parser.add_argument("--dry-run", action="store_true")

    uninstall_parser = subparsers.add_parser("uninstall", help="uninstall one or more skills")
    uninstall_parser.add_argument("skill_ids", nargs="+", help="registered skill id(s)")
    uninstall_parser.add_argument("--host", required=True, help=f"install selector: {', '.join(install_selectors())}")
    uninstall_parser.add_argument("--target-dir", type=Path, default=None, help="project root for project-scope targets")
    uninstall_parser.add_argument("--dry-run", action="store_true")

    verify_parser = subparsers.add_parser("verify", help="verify an installed skill's integrity")
    verify_parser.add_argument("installed_path", type=Path)

    update_parser = subparsers.add_parser("update", help="check for and install a newer sb release")
    update_parser.add_argument(
        "--channel", default="stable", help="release channel (only 'stable' is supported today)"
    )
    update_parser.add_argument(
        "--check", action="store_true", help="only check for an update, do not install it"
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
    if args.command == "install":
        return _cmd_install(args)
    if args.command == "uninstall":
        return _cmd_uninstall(args)
    if args.command == "verify":
        return cmd_verify(args.installed_path)
    if args.command == "update":
        return run_update(channel=args.channel, check_only=args.check)

    print(f"error: unknown command {args.command!r}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
