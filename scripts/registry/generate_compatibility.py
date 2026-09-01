from __future__ import annotations

from pathlib import Path

from scripts.registry.backfill_capabilities import load_catalog
from scripts.registry.canonical_manifest import (
    has_canonical_manifest_shape,
    load_canonical_manifest,
    validate_canonical_manifest,
)
from scripts.registry.composition_contracts import load_contracts
from scripts.registry.host_adapter import HOSTS, capability_support, validate_host_adapter_interface
from scripts.registry.load import load_registry
from scripts.release_info import read_distribution_version
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

# `host.*` capability ids (from capability_catalog.yaml's global `required`
# lists) mapped to the host_contracts.yaml capability family/families whose
# per-host support level gates that requirement. capability_families.yaml
# deliberately exempts `host.*` ids from its own (differently-scoped)
# provider-resolution mapping -- see its module docstring -- so this is a
# separate, purpose-built join for the compatibility matrix. Only ids that
# actually appear in some skill's global `required` list need an entry: those
# are exactly what's already surfaced in the "Required capabilities" column,
# and none of the catalog's `any_of` alternative paths reference `host.*`
# ids today. A `host.*` id that shows up in `required` without an entry here
# fails the build (see `_required_host_families`) instead of silently
# rendering the old blanket per-host profile.
HOST_CAPABILITY_FAMILIES: dict[str, tuple[str, ...]] = {
    "host.repository.read": ("read_repo",),
    "host.repository.read_write": ("read_repo", "write_repo"),
    "host.filesystem.read": ("read_repo",),
    "host.report.write": ("write_repo",),
    "host.role.isolation": ("task_isolation",),
    "host.ci.status": ("scm",),
    "host.pull_request.write": ("scm",),
    "host.issue_tracker.read": ("connectors",),
}

_SUPPORT_RANK = {"full": 0, "degraded": 1, "unsupported": 2}

HEADER = """# Compatibility matrix

<!-- GENERATED from skills.yaml + capability_catalog.yaml (canonical manifest) — do not edit; run make generate -->

Distribution version: **{version}**

| Skill | Invocation | Cursor | Claude | Codex | ChatGPT | Kiro | Generic | Host support envelope | Required capabilities | Write authority |
|-------|------------|--------|--------|-------|---------|------|---------|-----------------|----------------------|-----------------|
"""


def _host_profiles(root: Path, *, canonical: bool) -> tuple[dict[str, str], dict[str, str], str]:
    path = root / "scripts/registry/host_contracts.yaml"
    if not path.is_file():
        if canonical:
            raise ValueError("host contracts required for canonical compatibility output")
        surfaces = {host: "unsupported" for host in HOSTS}
        profiles = {host: "unsupported" for host in HOSTS}
        return surfaces, profiles, "legacy: unknown"

    adapter_errors = validate_host_adapter_interface(root)
    if adapter_errors:
        raise ValueError("\n".join(adapter_errors))
    raw = require_mapping(load_unique_yaml_file(path), "host contracts")
    hosts = require_mapping(raw.get("hosts"), "host contracts.hosts")
    surfaces: dict[str, str] = {}
    profiles: dict[str, str] = {}
    profile_lines: list[str] = []
    order = {"full": 0, "degraded": 1, "unsupported": 2}
    for host in sorted(HOSTS):
        config = require_mapping(hosts.get(host), f"host contracts.hosts.{host}")
        support = require_mapping(config.get("support"), f"host contracts.hosts.{host}.support")
        levels = sorted({str(value) for value in support.values()}, key=lambda value: order.get(value, 99))
        surfaces[host] = str(config.get("adapter", host))
        profile = "/".join(levels)
        profiles[host] = profile
        profile_lines.append(f"{host}: {profile}")
    return surfaces, profiles, "; ".join(profile_lines)


def _load_optional_canonical_manifest(root: Path) -> dict | None:
    """Load the canonical manifest, preserving legacy fixture compatibility.

    Older registry-only fixtures still use ``skills.yaml`` without canonical
    skill metadata. They should keep rendering the legacy matrix. Once a file
    contains canonical markers, however, malformed metadata must fail closed
    instead of being hidden by the legacy fallback.
    """
    path = root / "skills.yaml"
    if not path.is_file():
        return None
    raw = require_mapping(load_unique_yaml_file(path), "skills.yaml root")
    canonical_marker = has_canonical_manifest_shape(raw)
    if not canonical_marker:
        return None
    errors = validate_canonical_manifest(root)
    if errors:
        raise ValueError("\n".join(errors))
    return load_canonical_manifest(root)


def _cell(value: object) -> str:
    """Escape dynamic values so generated Markdown cannot change its table shape."""
    escaped: list[str] = []
    for char in str(value):
        codepoint = ord(char)
        if char == "\\":
            escaped.append("\\\\")
        elif char in {"|", "`", "[", "]", "(", ")", "<", ">"}:
            escaped.append("\\" + char)
        elif codepoint < 0x20 or codepoint == 0x7F:
            escaped.append(f"\\x{codepoint:02x}")
        else:
            escaped.append(char)
    return "".join(escaped)


def _required_host_families(required: list[str]) -> set[str]:
    """Resolve a skill's global `required` capability ids to host_contracts families.

    Non-`host.*` ids (gitlab.*, slack.*, telemetry.*, ...) aren't governed by
    host_contracts.yaml's per-host family model, so they're skipped here.
    """
    families: set[str] = set()
    for capability in required:
        if not capability.startswith("host."):
            continue
        mapped = HOST_CAPABILITY_FAMILIES.get(capability)
        if mapped is None:
            raise ValueError(
                f"host capability {capability!r} has no entry in "
                "HOST_CAPABILITY_FAMILIES (scripts/registry/generate_compatibility.py); "
                "add one so the compatibility matrix can gate it per host",
            )
        families.update(mapped)
    return families


def _worst_required_support(root: Path, host: str, families: set[str]) -> str | None:
    """Worst (lowest) support level `host` offers across `families`, or None if empty."""
    if not families:
        return None
    levels = [capability_support(root, host, family) for family in families]
    return max(levels, key=lambda level: _SUPPORT_RANK[level])


def render_compatibility_matrix(root: Path) -> str:
    registry = load_registry(root)
    capabilities = load_catalog(root / "scripts/registry/capability_catalog.yaml")
    _, _, _, contracts = load_contracts(root / "skills.yaml")
    version = read_distribution_version(root)
    manifest = _load_optional_canonical_manifest(root)
    host_surfaces, host_profiles, support_profile = _host_profiles(root, canonical=manifest is not None)

    lines = [HEADER.format(version=version).rstrip()]
    for skill_id, entry in sorted(registry.skills.items()):
        cap = capabilities.get(skill_id, {})
        contract = contracts.get(skill_id)
        required_list = cap.get("required", []) if isinstance(cap, dict) else []
        any_of = cap.get("any_of", []) if isinstance(cap, dict) else []
        global_required = ", ".join(str(item) for item in required_list)
        required_alternatives: list[str] = []
        for path in any_of if isinstance(any_of, list) else []:
            if isinstance(path, dict):
                name = str(path.get("name", "path"))
                path_required = path.get("required", [])
                if isinstance(path_required, list):
                    required_alternatives.append(
                        f"{name}: {' + '.join(str(item) for item in path_required)}",
                    )
        alternative_required = " OR ".join(required_alternatives)
        if global_required and alternative_required:
            required = f"{global_required} AND ({alternative_required})"
        else:
            required = global_required or alternative_required or "—"
        write_authority = contract.write_authority if contract else "—"
        canonical_skill = manifest.get("skills", {}).get(skill_id) if manifest else None
        supported_hosts = (
            set(canonical_skill.get("supported_hosts", []))
            if isinstance(canonical_skill, dict)
            else {"cursor", "claude", "kiro"}
        )
        required_families = _required_host_families(required_list) if isinstance(required_list, list) else set()

        def host_cell(host: str, surface: str) -> str:
            if host not in supported_hosts:
                return "unsupported"
            if support_profile == "legacy: unknown":
                return surface
            worst = _worst_required_support(root, host, required_families)
            if worst is None or worst == "full":
                return f"{surface} ({host_profiles.get(host, 'unknown')})"
            # This skill requires a capability that `host` only offers below
            # `full` (or not at all) -- surface that specific gap instead of
            # the blanket all-families profile every skill used to render.
            return f"{surface} ({worst})"

        lines.append(
            f"| {_cell(skill_id)} | {_cell(entry.invocation)} | "
            f"{_cell(host_cell('cursor', entry.hosts['cursor'].discovery))} | "
            f"{_cell(host_cell('claude', 'yes' if entry.hosts['claude'].install else 'no'))} | "
            f"{_cell(host_cell('codex', host_surfaces['codex']))} | "
            f"{_cell(host_cell('chatgpt', host_surfaces['chatgpt']))} | "
            f"{_cell(host_cell('kiro', entry.hosts['kiro'].discovery))} | "
            f"{_cell(host_cell('generic', host_surfaces['generic']))} | "
            f"{_cell(support_profile)} | {_cell(required)} | {_cell(write_authority)} |",
        )
    return "\n".join(lines) + "\n"
