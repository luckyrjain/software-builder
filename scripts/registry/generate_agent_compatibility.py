"""Generated agent-compatibility documentation (Candidate 11 of
docs/superpowers/specs/2026-08-31-universal-agent-compatibility-design.md).

Renders docs/agent-compatibility.md and README.md's compatibility summary section from
agent-hosts.yaml + skills.yaml, wired into the existing `make generate`/`generate --check`
pipeline (scripts/registry/cli.py) rather than a standalone script -- the spec's own illustrative
"render_agent_support.py --check" names a *behavior* (deterministic generation with a drift
check), and this repo already has exactly that behavior for every other generated artifact
(cursor rules, Kiro steering, the existing host_contracts.yaml-driven compatibility matrix, ...).
Building a second, parallel generate/--check command here would be the same "second engine" the
spec's Section 11 tells Candidate 4 not to build, applied to documentation instead of capability
resolution.

Distinct from the pre-existing generate_compatibility.py, which renders
generated/catalogue/compatibility-matrix.md from host_contracts.yaml/host_adapter.py (the
older, adapter-generation-focused registry, spec Section 28's "distribution channel"). This module
is agent-hosts.yaml-specific: host discovery, verification, evidence, and the Candidate 4 resolver's
host x skill results -- the newer, evidence-gated registry this whole Phase 2 effort is about.
Per spec Section 45, README gets only a concise summary table; full detail (per spec Section 43:
discovery support, verification, surface, scope, isolation, limitations, evidence) lives in
docs/agent-compatibility.md. No invented compatibility percentages (Section 43) appear in either.
"""

from __future__ import annotations

from pathlib import Path

from scripts.registry.compatibility_resolver import resolve_matrix
from scripts.registry.generate_docs import escape_table_cell as _cell
from scripts.registry.generate_docs import update_marker_block
from scripts.registry.host_registry import HostRegistry, HostSpec, parse_host_registry
from scripts.registry.models import Registry
from scripts.registry.schema import parse_registry

README_AGENT_COMPATIBILITY_START = "<!-- agent-compatibility:start -->"
README_AGENT_COMPATIBILITY_END = "<!-- agent-compatibility:end -->"

_DOC_HEADER = """# Agent compatibility

<!-- GENERATED from agent-hosts.yaml + skills.yaml — do not edit; run make generate -->

This document is the detailed companion to README.md's compatibility summary. It states only
what is declared in `agent-hosts.yaml`, verified by whatever evidence is actually recorded there
-- not invented compatibility percentages (spec Section 43).

## Hosts
"""

_MATRIX_HEADER = """
## Host × skill compatibility

`READY`/`DEGRADED` require both a satisfied capability requirement and a `VERIFIED` host; an
`UNVERIFIED` or `CONFLICTED` host downgrades what would otherwise be READY/DEGRADED, and a
concrete missing capability (`BLOCKED`) always takes precedence, matching
`scripts/registry/compatibility_resolver.py`'s combination rule.

| Host | Skill | Status | Missing capability |
|------|-------|--------|---------------------|
"""


def _surface_summary(host: HostSpec) -> str:
    parts = []
    for surface in host.surfaces:
        targets = ", ".join(binding.target.id for binding in sorted(surface.discovery, key=lambda b: b.precedence))
        parts.append(f"{surface.kind} ({targets})")
    return "; ".join(parts) if parts else "none declared"


def _evidence_summary(host: HostSpec) -> str:
    if not host.evidence:
        return "none recorded"
    return "; ".join(f"{entry.kind}: {entry.reference}" for entry in host.evidence)


def _capabilities_summary(host: HostSpec) -> str:
    if not host.capabilities.values:
        return "none declared"
    return ", ".join(f"{name}={state}" for name, state in sorted(host.capabilities.values))


def render_agent_compatibility_doc(host_registry: HostRegistry, registry: Registry) -> str:
    lines = [_DOC_HEADER.rstrip("\n")]
    for host_id in sorted(host_registry.hosts):
        host = host_registry.hosts[host_id]
        lines.append(f"\n### {_cell(host_id)}")
        lines.append(f"- **Verification:** {_cell(host.verification)}")
        lines.append(f"- **Maintainer support:** {_cell(host.maintainer_support)}")
        lines.append(f"- **Isolation:** {_cell(host.isolation.mode)}")
        lines.append(f"- **Discovery surfaces:** {_cell(_surface_summary(host))}")
        lines.append(f"- **Capabilities:** {_cell(_capabilities_summary(host))}")
        lines.append(f"- **Evidence:** {_cell(_evidence_summary(host))}")
        if host.constraints.values:
            lines.append(f"- **Constraints:** {_cell(', '.join(host.constraints.values))}")

    aliases = sorted(host_registry.aliases)
    if aliases:
        lines.append("\n## Aliases\n")
        lines.append("| Alias | Resolves to |")
        lines.append("|-------|-------------|")
        for alias_id in aliases:
            lines.append(f"| {_cell(alias_id)} | {_cell(host_registry.aliases[alias_id].id)} |")

    lines.append(_MATRIX_HEADER.rstrip("\n"))
    for result in resolve_matrix(host_registry, registry):
        missing = ", ".join(result.missing_required) if result.missing_required else "—"
        lines.append(
            f"| {_cell(result.host_id)} | {_cell(result.skill_id)} | {_cell(result.status)} | "
            f"{_cell(missing)} |"
        )
    return "\n".join(lines) + "\n"


def render_readme_agent_compatibility_section(host_registry: HostRegistry) -> str:
    """The "concise support table" spec Section 45 says README may contain -- verification state
    and maintainer support only, no per-skill detail and no evidence text. Full detail is always
    one link away in docs/agent-compatibility.md."""
    lines = [
        "\n\nCanonical, evidence-gated host compatibility (see "
        "[docs/agent-compatibility.md](docs/agent-compatibility.md) for full detail):\n",
        "| Host | Verification | Maintainer support |",
        "|------|--------------|---------------------|",
    ]
    for host_id in sorted(host_registry.hosts):
        host = host_registry.hosts[host_id]
        lines.append(f"| {_cell(host_id)} | {_cell(host.verification)} | {_cell(host.maintainer_support)} |")
    return "\n".join(lines) + "\n"


def update_readme_agent_compatibility_section(readme: str, host_registry: HostRegistry) -> str:
    return update_marker_block(
        readme,
        README_AGENT_COMPATIBILITY_START,
        README_AGENT_COMPATIBILITY_END,
        render_readme_agent_compatibility_section(host_registry),
    )


def load_host_registry_and_registry(root: Path) -> tuple[HostRegistry, Registry]:
    return parse_host_registry(root / "agent-hosts.yaml"), parse_registry(root / "skills.yaml")
