from __future__ import annotations

from pathlib import Path

from scripts.registry.backfill_capabilities import load_catalog
from scripts.registry.canonical_manifest import load_canonical_manifest, validate_canonical_manifest
from scripts.registry.composition_contracts import load_contracts
from scripts.registry.host_adapter import HOSTS, validate_host_adapter_interface
from scripts.registry.load import load_registry
from scripts.release_info import read_distribution_version
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

HEADER = """# Compatibility matrix

<!-- GENERATED from skills.yaml + capability_catalog.yaml (canonical manifest) — do not edit; run make generate -->

Distribution version: **{version}**

| Skill | Invocation | Cursor | Claude | Codex | ChatGPT | Kiro | Generic | Host support envelope | Required capabilities | Write authority |
|-------|------------|--------|--------|-------|---------|------|---------|-----------------|----------------------|-----------------|
"""


def _host_profiles(root: Path) -> tuple[dict[str, str], dict[str, str], str]:
    path = root / "scripts/registry/host_contracts.yaml"
    if not path.is_file():
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
    skills = raw.get("skills")
    canonical_marker = "contracts" in raw
    if isinstance(skills, dict):
        canonical_marker = canonical_marker or any(
            isinstance(skill, dict)
            and {"version", "type", "authority", "supported_hosts"} & set(skill)
            for skill in skills.values()
        )
    if not canonical_marker:
        return None
    errors = validate_canonical_manifest(root)
    if errors:
        raise ValueError("\n".join(errors))
    return load_canonical_manifest(root)


def _cell(value: object) -> str:
    """Escape dynamic values so generated Markdown cannot change its table shape."""
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("|", "\\|")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
    )


def render_compatibility_matrix(root: Path) -> str:
    registry = load_registry(root)
    capabilities = load_catalog(root / "scripts/registry/capability_catalog.yaml")
    _, _, _, contracts = load_contracts(root / "skills.yaml")
    version = read_distribution_version(root)
    host_surfaces, host_profiles, support_profile = _host_profiles(root)
    manifest = _load_optional_canonical_manifest(root)

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

        def host_cell(host: str, surface: str) -> str:
            if host not in supported_hosts:
                return "unsupported"
            if support_profile == "legacy: unknown":
                return surface
            return f"{surface} ({host_profiles.get(host, 'unknown')})"

        lines.append(
            f"| `{_cell(skill_id)}` | {_cell(entry.invocation)} | "
            f"{_cell(host_cell('cursor', entry.hosts.cursor.discovery))} | "
            f"{_cell(host_cell('claude', 'yes' if entry.hosts.claude.install else 'no'))} | "
            f"{_cell(host_cell('codex', host_surfaces['codex']))} | "
            f"{_cell(host_cell('chatgpt', host_surfaces['chatgpt']))} | "
            f"{_cell(host_cell('kiro', entry.hosts.kiro.discovery))} | "
            f"{_cell(host_cell('generic', host_surfaces['generic']))} | "
            f"{_cell(support_profile)} | {_cell(required)} | {_cell(write_authority)} |",
        )
    return "\n".join(lines) + "\n"
