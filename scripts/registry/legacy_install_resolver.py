"""Destination resolution for scripts/install.sh's legacy --agent selectors, driven by
agent-hosts.yaml's targets instead of hard-coded Bash `case` statements (Candidate 5 of
docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md).

This module is deliberately a faithful, tested port of install.sh's *existing* dest_roots()/
host_label_for_dest() Bash logic -- including one real quirk it preserves rather than "fixes": the
`claude-user` selector always resolves against $HOME, ignoring --target-dir entirely, while every
other selector prefers --target-dir when given. Candidate 5's own exit bar is "golden Cursor/Claude
tests unchanged", not "clean up install.sh's selector semantics" -- changing that quirk, even for an
untested edge case, would risk violating AC-06/AC-07's behavioral-compatibility guarantee. A future
candidate can revisit it once new golden tests are written to intentionally lock in a change.

Only the four legacy selectors (cursor, cursor-project, claude-user, claude-project) plus `all` are
resolved here, per Candidate 5's "Only legacy hosts enabled initially" -- new host selectors are
Candidate 7's job.
"""

from __future__ import annotations

from pathlib import Path

from scripts.registry.host_registry import HostRegistry, TargetSpec

LEGACY_AGENT_SELECTORS = frozenset({"cursor", "cursor-project", "claude-user", "claude-project", "all"})

# Each legacy selector's (target used when --target-dir is absent, target used when given).
# cursor/cursor-project are identical in install.sh today (both prefer the project target when
# --target-dir is given, else fall back to the user target); claude-user is the quirk described
# above; claude-project prefers the project target when given, else falls back to the user target.
_SINGLE_DEST_ROUTING: dict[str, tuple[str, str]] = {
    "cursor": ("cursor-user", "cursor-project"),
    "cursor-project": ("cursor-user", "cursor-project"),
    "claude-user": ("claude-user", "claude-user"),
    "claude-project": ("claude-user", "claude-project"),
}


def _resolve_target_path(target: TargetSpec, *, home: Path, target_dir: Path | None) -> Path:
    if target.scope == "user":
        # host_registry.py's own _validate_target_path already guarantees a user-scope path
        # starts with exactly "~/" -- see host_registry.py's ALLOWED_SCOPES validation.
        return home / target.path[len("~/") :]
    base = target_dir if target_dir is not None else home
    return base / target.path[len("{project_root}/") :]


def _resolve_single_destination(
    host_registry: HostRegistry,
    routing: tuple[str, str],
    *,
    home: Path,
    target_dir: Path | None,
) -> Path:
    no_dir_target_id, with_dir_target_id = routing
    target_id = with_dir_target_id if target_dir is not None else no_dir_target_id
    target = host_registry.targets[target_id]
    return _resolve_target_path(target, home=home, target_dir=target_dir)


def host_label_for_dest(dest_root: Path, *, home: Path) -> str:
    """Port of install.sh's host_label_for_dest(): derived from the *resolved path itself*, not
    from which --agent selector produced it -- e.g. `--agent cursor --target-dir X` resolves to a
    non-$HOME path and is labeled "cursor-project", matching today's Bash behavior exactly."""
    if dest_root == home / ".cursor" / "skills":
        return "cursor"
    if dest_root == home / ".claude" / "skills":
        return "claude-user"
    if dest_root.as_posix().endswith("/.cursor/skills"):
        return "cursor-project"
    return "claude-project"


def resolve_legacy_install_destinations(
    host_registry: HostRegistry,
    agent: str,
    *,
    home: Path,
    target_dir: Path | None,
) -> list[tuple[Path, str]]:
    """Every (destination root, host label) pair for one legacy --agent selector, in the same
    order install.sh's own dest_roots() prints them."""
    if agent not in LEGACY_AGENT_SELECTORS:
        raise ValueError(f"unknown --agent {agent!r} (expected one of {sorted(LEGACY_AGENT_SELECTORS)})")

    if agent == "all":
        destinations = [
            _resolve_single_destination(host_registry, _SINGLE_DEST_ROUTING["cursor"], home=home, target_dir=target_dir),
            _resolve_single_destination(host_registry, _SINGLE_DEST_ROUTING["claude-project"], home=home, target_dir=target_dir),
        ]
    else:
        destinations = [
            _resolve_single_destination(host_registry, _SINGLE_DEST_ROUTING[agent], home=home, target_dir=target_dir),
        ]
    return [(dest, host_label_for_dest(dest, home=home)) for dest in destinations]
