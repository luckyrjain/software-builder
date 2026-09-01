"""Destination resolution for install.sh's `--agent agents` selector (Candidate 7 of
docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md).

Unlike scripts/registry/legacy_install_resolver.py's four selectors, `agents` is not routed
through any specific host's target list -- it resolves directly to the universal Agent Skills
target (agents-user/agents-project in agent-hosts.yaml, per spec Section 31), the shared,
multi-tool discovery directory `.agents/skills`. This is new installer surface, not a port of
existing Bash behavior, so it carries no inherited quirk to preserve: it simply prefers the
project target when --target-dir is given, else the user target -- the same precedence every
legacy multi-target selector already uses.
"""

from __future__ import annotations

from pathlib import Path

from scripts.registry.host_registry import HostRegistry, resolve_target_path

UNIVERSAL_AGENT_SELECTOR = "agents"


def resolve_universal_install_destination(
    host_registry: HostRegistry,
    *,
    home: Path,
    target_dir: Path | None,
) -> tuple[Path, str]:
    """The universal target's (destination root, host label) pair. The label is the target id
    itself (agents-user/agents-project) rather than a product name, since this destination isn't
    tied to any one host's identity."""
    target_id = "agents-project" if target_dir is not None else "agents-user"
    try:
        target = host_registry.targets[target_id]
    except KeyError:
        raise ValueError(
            f"agent-hosts.yaml has no {target_id!r} target -- the universal `agents` selector"
            " requires it (spec Section 31)"
        ) from None
    dest = resolve_target_path(target, home=home, target_dir=target_dir)
    return dest, target_id
