"""One module answering "where does `install.sh --agent X` write, and under what host label".

Selector routing used to be spread across five places: install.sh's `case` allowlist, two
sibling resolver modules named as if they were a seam (they had incompatible signatures, so the
caller did the dispatch), a reverse-derivation of the host label from hard-coded path literals,
and a third label -> (host, target) table in shadow_detector.py. This module is the single seam:
one data table of selectors, one public resolver returning `(destination, host label)` directly,
and one label -> target mapping that shadow detection reads instead of re-declaring.

Destinations themselves still come from agent-hosts.yaml -- only the selector-to-target routing
and the label vocabulary live here, because those are installer-CLI facts, not host-registry
facts.

One inherited quirk is preserved verbatim as data rather than "fixed": the `claude-user` selector
always resolves against $HOME and ignores --target-dir entirely, while every other selector
prefers --target-dir when it is given. install.sh has always behaved this way; the golden tests in
scripts/tests/test_install_legacy_golden.py lock it in, and changing it is a deliberate,
separately-tested decision rather than a refactoring side effect.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts.registry.host_registry import HostRegistry, resolve_target_path


@dataclass(frozen=True)
class Route:
    """One destination of a selector: which agent-hosts.yaml target it resolves to with and
    without --target-dir. The two ids are equal for a selector that ignores --target-dir."""

    without_target_dir: str
    with_target_dir: str

    def target_id(self, *, target_dir: Path | None) -> str:
        return self.with_target_dir if target_dir is not None else self.without_target_dir


_CURSOR = Route("cursor-user", "cursor-project")
# The preserved quirk: both branches are the user-scope target, so --target-dir is ignored.
_CLAUDE_USER = Route("claude-user", "claude-user")
_CLAUDE_PROJECT = Route("claude-user", "claude-project")
_AGENTS = Route("agents-user", "agents-project")

# Declaration order is the order install.sh prints in its unknown-selector error and the order
# `all` writes its two destinations in -- both are golden.
SELECTORS: dict[str, tuple[Route, ...]] = {
    "cursor": (_CURSOR,),
    "cursor-project": (_CURSOR,),
    "claude-user": (_CLAUDE_USER,),
    "claude-project": (_CLAUDE_PROJECT,),
    "all": (_CURSOR, _CLAUDE_PROJECT),
    "agents": (_AGENTS,),
}

# Host label written into each install manifest and printed by install.sh. Every target labels
# itself except cursor-user, which install.sh has always called plain "cursor".
TARGET_LABELS: dict[str, str] = {
    "cursor-user": "cursor",
    "cursor-project": "cursor-project",
    "claude-user": "claude-user",
    "claude-project": "claude-project",
    "agents-user": "agents-user",
    "agents-project": "agents-project",
}

TARGET_ID_BY_LABEL: dict[str, str] = {label: target for target, label in TARGET_LABELS.items()}

# agent-hosts.yaml targets no selector can reach, each with the reason it is deliberately
# unreachable. `check_target_reachability` fails on any target that is neither routed nor listed
# here, so adding a target to the registry can no longer silently produce an uninstallable host.
UNREACHABLE_TARGETS: dict[str, str] = {
    "kiro-generated": (
        "generated in place by `make generate` (scripts/registry/generate_kiro.py) at a fixed "
        "repo-root path, never installed to a user or target-repo directory -- see the target's "
        "own note in agent-hosts.yaml and the kiro host's `not install.sh-resolvable` constraint"
    ),
    "github-copilot-user": (
        "modeled from GitHub's published discovery paths but not yet exposed as a selector; "
        "Copilot also reads the universal target, which `--agent agents` already installs to"
    ),
    "github-copilot-project": (
        "modeled from GitHub's published discovery paths but not yet exposed as a selector; "
        "Copilot also reads the universal target, which `--agent agents` already installs to"
    ),
}


def install_selectors() -> list[str]:
    """Every valid `--agent` value, in the order install.sh reports them."""
    return list(SELECTORS)


def routed_target_ids() -> set[str]:
    """Every agent-hosts.yaml target id some selector can install to."""
    return {
        target_id
        for routes in SELECTORS.values()
        for route in routes
        for target_id in (route.without_target_dir, route.with_target_dir)
    }


def label_for_target(target_id: str) -> str:
    return TARGET_LABELS.get(target_id, target_id)


def resolve_install_destinations(
    host_registry: HostRegistry,
    agent: str,
    *,
    home: Path,
    target_dir: Path | None,
) -> list[tuple[Path, str]]:
    """Every (destination root, host label) pair one `--agent` selector installs to, in the order
    install.sh writes them."""
    routes = SELECTORS.get(agent)
    if routes is None:
        raise ValueError(f"unknown --agent {agent!r} (expected one of {install_selectors()})")

    destinations: list[tuple[Path, str]] = []
    for route in routes:
        target_id = route.target_id(target_dir=target_dir)
        target = host_registry.targets.get(target_id)
        if target is None:
            raise ValueError(
                f"agent-hosts.yaml has no {target_id!r} target -- required by --agent {agent!r}"
            )
        dest = resolve_target_path(target, home=home, target_dir=target_dir)
        destinations.append((dest, label_for_target(target_id)))
    return destinations


def host_and_target_for_label(host_registry: HostRegistry, host_label: str) -> tuple[str, str] | None:
    """The (host id, target id) a printed host label belongs to, or None when no host in
    agent-hosts.yaml declares that target as a discovery root.

    None is the ordinary answer for the universal `agents-user`/`agents-project` labels: the
    universal target is target-only by design, so there is no host whose discovery precedence a
    write to it could be compared against.
    """
    target_id = TARGET_ID_BY_LABEL.get(host_label)
    if target_id is None:
        return None
    for host_id in sorted(host_registry.hosts):
        host = host_registry.hosts[host_id]
        if any(
            binding.target.id == target_id
            for surface in host.surfaces
            for binding in surface.discovery
        ):
            return host_id, target_id
    return None


def check_target_reachability(host_registry: HostRegistry) -> list[str]:
    """Errors when agent-hosts.yaml and this module's routing have drifted apart.

    Adding a target to the registry without a selector, or routing a selector to a target the
    registry does not declare, both used to be silent; so did leaving a stale entry in
    UNREACHABLE_TARGETS after a selector finally reached it.
    """
    errors: list[str] = []
    declared = set(host_registry.targets)
    routed = routed_target_ids()

    for target_id in sorted(routed - declared):
        errors.append(
            f"selector routing names {target_id!r}, which agent-hosts.yaml does not declare"
        )
    for target_id in sorted(declared - routed - set(UNREACHABLE_TARGETS)):
        errors.append(
            f"agent-hosts.yaml target {target_id!r} is not reachable from any --agent selector; "
            "add a selector or record it in install_resolver.UNREACHABLE_TARGETS with a reason"
        )
    for target_id in sorted(set(UNREACHABLE_TARGETS) & routed):
        errors.append(
            f"{target_id!r} is listed in install_resolver.UNREACHABLE_TARGETS but a selector "
            "now reaches it -- remove the stale entry"
        )
    for target_id in sorted(set(UNREACHABLE_TARGETS) - declared):
        errors.append(
            f"{target_id!r} is listed in install_resolver.UNREACHABLE_TARGETS but agent-hosts.yaml "
            "no longer declares it -- remove the stale entry"
        )
    return errors
