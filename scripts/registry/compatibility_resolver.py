"""Host x skill compatibility resolution (Candidate 4 of the universal-agent-compatibility design,
docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md).

Reuses scripts/registry/capability_engine.py's `capability_status` (skills.yaml's required/optional/
any_of capability resolution semantics, originally doctor.py's private helper, extracted so this
module and doctor.py -- which now imports this module directly for Candidate 10's --agent support --
don't import each other) rather than building a second one, per that spec's Section 11.

Scope of this first pass, deliberately bounded (documented rather than silently assumed):

- Capability availability is resolved at the HOST level. agent-hosts.yaml's HostSpec.capabilities is
  not yet nested per-surface (see Candidate 2's schema), so this resolver cannot yet answer "is this
  capability available on the cloud surface but not the local surface" -- only "is it available on this
  host at all". `surface`/`scope` are still meaningful for *discovery* (below), just not yet for
  capability differentiation. A later candidate that extends HostSpec to carry per-surface capabilities
  should extend `available_capabilities` here to take a surface parameter.
- `discovery` here means "does this host have at least one surface with a resolvable install target" --
  agent-hosts.yaml's schema models discovery at the target/surface level, not per skill, so it cannot
  yet answer "is skill X specifically reachable" independent of every other skill on that host.
- `constraints` (catalog/layout limits, spec Section 22) has no representation in agent-hosts.yaml's
  schema yet, so this resolver does not evaluate it. A host with real catalog constraints needs a later
  candidate to add that schema before this resolver can enforce it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from scripts.registry.capability_engine import capability_status as _capability_status
from scripts.registry.host_registry import HostRegistry, HostSpec
from scripts.registry.models import CapabilityPath, Registry, SkillEntry

# Maps scripts/registry/host_adapter.py's coarser adapter-generation capability vocabulary
# (host_contracts.yaml's capability_families) onto the finer-grained host.* vocabulary
# skills.yaml's per-skill capabilities and agent-hosts.yaml's HostSpec.capabilities already share.
# Every host_adapter.CAPABILITIES entry has an explicit home here -- none are left unmapped -- so the
# two vocabularies are no longer parallel, unreconciled sources (Candidate 2's deferred exit bar,
# closed here per Candidate 4's own text).
#
# discover_files/read_repo/write_repo/browser reuse names skills.yaml's capability requirements
# already use. git/scm/subagents/task_isolation/terminal/connectors have no pre-existing skills.yaml
# capability name (no registered skill currently requires them), so this introduces their host.*
# names for the first time -- chosen to be self-describing and consistent with the existing
# `host.<domain>.<verb>` convention, not to claim any host actually supports them yet (that's still
# governed by each host's own agent-hosts.yaml capabilities: entry).
HOST_ADAPTER_CAPABILITY_MAP: dict[str, str] = {
    "discover_files": "host.filesystem.read",
    "read_repo": "host.repository.read",
    "write_repo": "host.repository.read_write",
    "git": "host.git.cli",
    "scm": "host.scm.api",
    "subagents": "host.subagent.spawn",
    "task_isolation": "host.task.isolation",
    "terminal": "host.terminal.execute",
    "browser": "host.browser.automation",
    "connectors": "host.connectors.access",
}

def _combine_status(capability_status: str, host_verification: str) -> str:
    """Combine doctor.py's capability-resolution outcome with the host's own verification state
    into the spec's Section 10 "Resolved skill status" (READY/DEGRADED/BLOCKED/UNVERIFIED/CONFLICTED).

    A concrete capability BLOCKED is the most informative signal (it names exactly which capability is
    missing) and always wins, regardless of host verification. Otherwise, a CONFLICTED or UNVERIFIED
    host cannot make a READY/DEGRADED claim credible -- Section 26's promotion gate says a host isn't
    trusted until it has earned VERIFIED status with runtime evidence. VERIFIED and STALE hosts both
    let the capability engine's own DEGRADED/READY answer stand: per Section 25, staleness blocks
    *promotion* to first-class, it must not retroactively make an already-working skill unusable.
    """
    if capability_status == "BLOCKED":
        return "BLOCKED"
    if host_verification == "CONFLICTED":
        return "CONFLICTED"
    if host_verification == "UNVERIFIED":
        return "UNVERIFIED"
    return capability_status


@dataclass(frozen=True)
class CompatibilityResult:
    host_id: str
    skill_id: str
    status: str
    capability_status: str
    host_verification: str
    missing_required: list[str] = field(default_factory=list)
    missing_optional: list[str] = field(default_factory=list)
    active_path: CapabilityPath | None = None
    discoverable: bool = False


class UnknownHostError(ValueError):
    pass


class UnknownSkillError(ValueError):
    pass


def resolve_host(host_registry: HostRegistry, host_id: str) -> HostSpec:
    """Resolve a host id, following one alias hop if `host_id` names an alias rather than a host.

    Alias-to-alias chains are already flattened by parse_host_registry's own resolution (host_registry.py
    `_resolve_aliases`), so `host_registry.aliases` always maps directly to a `HostSpec`, never another
    alias -- this needs at most the two lookups below, never a loop.
    """
    if host_id in host_registry.hosts:
        return host_registry.hosts[host_id]
    if host_id in host_registry.aliases:
        return host_registry.aliases[host_id]
    raise UnknownHostError(
        f"unknown host {host_id!r} (known hosts: {sorted(host_registry.hosts)}, "
        f"known aliases: {sorted(host_registry.aliases)})"
    )


def available_capabilities(host: HostSpec) -> frozenset[str]:
    """The capability names this host currently satisfies -- AVAILABLE only.

    UNKNOWN and UNAVAILABLE capabilities are excluded by CapabilitySpec.available itself (spec
    Section 12: UNKNOWN must not satisfy a required capability), so no extra fail-closed logic is
    needed here beyond delegating to it.
    """
    return host.capabilities.available


def is_discoverable(host: HostSpec) -> bool:
    """Whether this host has at least one surface with a resolvable install target.

    Host-level, not skill-level -- see this module's docstring for why agent-hosts.yaml's current
    schema can't yet answer "is skill X specifically reachable" independent of every other skill.

    Always True today: host_registry.py's own parser (_parse_surfaces/_parse_discovery) already
    rejects a host with an empty surfaces list or a surface with an empty discovery list, so a
    successfully-parsed HostSpec is unconditionally discoverable by construction. This function still
    exists (rather than a hardcoded True) for when a future schema relaxes that constraint.
    """
    return any(surface.discovery for surface in host.surfaces)


def resolve_capability(entry: SkillEntry, available: frozenset[str]) -> tuple[str, list[str], list[str], CapabilityPath | None]:
    """Reuses doctor.py's exact capability-resolution engine -- see this module's docstring."""
    optional_names = [item.name for item in entry.capabilities.optional]
    missing_required, missing_optional, status, active_path = _capability_status(
        entry.capabilities.required,
        optional_names,
        entry.capabilities.any_of,
        set(available),
    )
    return status, missing_required, missing_optional, active_path


def resolve(host_registry: HostRegistry, registry: Registry, host_id: str, skill_id: str) -> CompatibilityResult:
    """Compute one host x skill compatibility result.

    `capability_status` is doctor.py's engine's own {UNSPECIFIED, BLOCKED, DEGRADED, READY} outcome
    (UNSPECIFIED never occurs here since `available` is always a concrete set, never None, when driven
    by a HostSpec). `status` is that outcome combined with the host's own verification state -- see
    `_combine_status`.
    """
    host = resolve_host(host_registry, host_id)
    entry = registry.skills.get(skill_id)
    if entry is None:
        raise UnknownSkillError(f"unknown skill {skill_id!r}")

    available = available_capabilities(host)
    capability_status, missing_required, missing_optional, active_path = resolve_capability(entry, available)
    status = _combine_status(capability_status, host.verification)

    return CompatibilityResult(
        host_id=host_id,
        skill_id=skill_id,
        status=status,
        capability_status=capability_status,
        host_verification=host.verification,
        missing_required=missing_required,
        missing_optional=missing_optional,
        active_path=active_path,
        discoverable=is_discoverable(host),
    )


def resolve_matrix(host_registry: HostRegistry, registry: Registry) -> list[CompatibilityResult]:
    """Every (host, skill) pair, sorted deterministically -- the spec's "host x skill results
    deterministic" exit bar for this candidate."""
    results: list[CompatibilityResult] = []
    for host_id in sorted(host_registry.hosts):
        for skill_id in sorted(registry.skills):
            results.append(resolve(host_registry, registry, host_id, skill_id))
    return results
