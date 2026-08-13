from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.registry.models import (
    CapabilitiesSpec,
    CapabilityOptional,
    CapabilityPath,
    CompositionSpec,
    HostClaude,
    HostCursor,
    HostKiro,
    Hosts,
    InstallSpec,
    LintSpec,
    Registry,
    SkillEntry,
)
from scripts.yaml_safety import load_unique_yaml_file

ALLOWED_RISK_CLASSES = frozenset(
    {"posting", "merge", "unattended", "read-only", "repository-write"},
)
AUTOMATION_ONLY_INVOCATION = "automation-only"
ALLOWED_INVOCATION = {"ambient", AUTOMATION_ONLY_INVOCATION}
ALLOWED_CURSOR_DISCOVERY = {"rule", "manual", "always"}
ALLOWED_KIRO_DISCOVERY = {"manual", "always"}
ALLOWED_COMPOSITION_MODE = {"invoke", "aggregate"}


def _require_mapping(data: Any, label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a mapping")
    return data


def parse_registry(path: Path) -> Registry:
    raw = load_unique_yaml_file(path)
    root = _require_mapping(raw, "skills.yaml root")
    schema_version = int(root.get("schema_version", 0))
    if schema_version != 1:
        raise ValueError(f"unsupported schema_version: {schema_version}")

    skills_raw = _require_mapping(root.get("skills"), "skills")
    skills: dict[str, SkillEntry] = {}
    for skill_id, entry_raw in skills_raw.items():
        entry = _require_mapping(entry_raw, f"skills.{skill_id}")
        invocation = str(entry.get("invocation", ""))
        if invocation not in ALLOWED_INVOCATION:
            raise ValueError(f"skills.{skill_id}.invocation invalid: {invocation!r}")

        hosts_raw = _require_mapping(entry.get("hosts"), f"skills.{skill_id}.hosts")
        cursor_raw = _require_mapping(hosts_raw.get("cursor"), f"skills.{skill_id}.hosts.cursor")
        kiro_raw = _require_mapping(hosts_raw.get("kiro"), f"skills.{skill_id}.hosts.kiro")
        claude_raw = hosts_raw.get("claude", {"install": True})
        claude_map = _require_mapping(claude_raw, f"skills.{skill_id}.hosts.claude")

        cursor_discovery = str(cursor_raw.get("discovery", ""))
        kiro_discovery = str(kiro_raw.get("discovery", ""))
        if cursor_discovery not in ALLOWED_CURSOR_DISCOVERY:
            raise ValueError(f"skills.{skill_id}.hosts.cursor.discovery invalid: {cursor_discovery!r}")
        if kiro_discovery not in ALLOWED_KIRO_DISCOVERY:
            raise ValueError(f"skills.{skill_id}.hosts.kiro.discovery invalid: {kiro_discovery!r}")

        install_raw = _require_mapping(entry.get("install"), f"skills.{skill_id}.install")
        requires = install_raw.get("requires", [])
        if not isinstance(requires, list):
            raise ValueError(f"skills.{skill_id}.install.requires must be a list")

        lint_raw = _require_mapping(entry.get("lint"), f"skills.{skill_id}.lint")

        composition_raw = entry.get("composition")
        composition = _parse_composition(
            composition_raw,
            skill_id,
            [str(item) for item in requires],
        )
        capabilities = _parse_capabilities(entry.get("capabilities"), skill_id)
        risk_class = _parse_risk_class(entry.get("risk_class"), skill_id)

        skills[skill_id] = SkillEntry(
            path=str(entry.get("path", skill_id)),
            category=str(entry.get("category", "")),
            invocation=invocation,
            hosts=Hosts(
                cursor=HostCursor(discovery=cursor_discovery),
                claude=HostClaude(install=bool(claude_map.get("install", True))),
                kiro=HostKiro(discovery=kiro_discovery),
            ),
            install=InstallSpec(requires=[str(item) for item in requires]),
            lint=LintSpec(
                skill_md_max_lines=int(lint_raw.get("skill_md_max_lines", 180)),
                target=str(lint_raw.get("target", skill_id)),
            ),
            composition=composition,
            capabilities=capabilities,
            risk_class=risk_class,
        )
    return Registry(schema_version=schema_version, skills=skills)


def _parse_composition(
    raw: Any,
    skill_id: str,
    install_requires: list[str],
) -> CompositionSpec:
    if raw is None:
        return CompositionSpec(invokes=list(install_requires), mode="invoke")
    composition = _require_mapping(raw, f"skills.{skill_id}.composition")
    mode = str(composition.get("mode", "invoke"))
    if mode not in ALLOWED_COMPOSITION_MODE:
        raise ValueError(f"skills.{skill_id}.composition.mode invalid: {mode!r}")

    invokes_raw = composition.get("invokes")
    if invokes_raw is None:
        invokes = [] if mode == "aggregate" else list(install_requires)
    else:
        if not isinstance(invokes_raw, list):
            raise ValueError(f"skills.{skill_id}.composition.invokes must be a list")
        invokes = [str(item) for item in invokes_raw]

    escalation_raw = composition.get("escalation_targets", [])
    if not isinstance(escalation_raw, list):
        raise ValueError(f"skills.{skill_id}.composition.escalation_targets must be a list")

    return CompositionSpec(
        invokes=invokes,
        escalation_targets=[str(item) for item in escalation_raw],
        mode=mode,
    )


def _parse_capabilities(raw: Any, skill_id: str) -> CapabilitiesSpec:
    if raw is None:
        return CapabilitiesSpec()
    capabilities = _require_mapping(raw, f"skills.{skill_id}.capabilities")

    required_raw = capabilities.get("required", [])
    if not isinstance(required_raw, list):
        raise ValueError(f"skills.{skill_id}.capabilities.required must be a list")

    optional_raw = capabilities.get("optional", [])
    if not isinstance(optional_raw, list):
        raise ValueError(f"skills.{skill_id}.capabilities.optional must be a list")
    optional = _parse_optional_capabilities(
        optional_raw,
        f"skills.{skill_id}.capabilities.optional",
    )

    any_of_raw = capabilities.get("any_of", [])
    if not isinstance(any_of_raw, list):
        raise ValueError(f"skills.{skill_id}.capabilities.any_of must be a list")
    any_of: list[CapabilityPath] = []
    for index, item in enumerate(any_of_raw):
        path = _require_mapping(item, f"skills.{skill_id}.capabilities.any_of[{index}]")
        name = str(path.get("name", ""))
        if not name:
            raise ValueError(f"skills.{skill_id}.capabilities.any_of[{index}].name is required")
        path_required = path.get("required", [])
        if not isinstance(path_required, list):
            raise ValueError(
                f"skills.{skill_id}.capabilities.any_of[{index}].required must be a list",
            )
        path_optional_raw = path.get("optional", [])
        if not isinstance(path_optional_raw, list):
            raise ValueError(
                f"skills.{skill_id}.capabilities.any_of[{index}].optional must be a list",
            )
        any_of.append(
            CapabilityPath(
                name=name,
                required=[str(item) for item in path_required],
                optional=_parse_optional_capabilities(
                    path_optional_raw,
                    f"skills.{skill_id}.capabilities.any_of[{index}].optional",
                ),
            ),
        )

    degraded_raw = capabilities.get("degraded_modes", {})
    if not isinstance(degraded_raw, dict):
        raise ValueError(f"skills.{skill_id}.capabilities.degraded_modes must be a mapping")
    degraded_modes = {str(key): str(value) for key, value in degraded_raw.items()}

    return CapabilitiesSpec(
        required=[str(item) for item in required_raw],
        optional=optional,
        any_of=any_of,
        degraded_modes=degraded_modes,
    )


def _parse_optional_capabilities(
    optional_raw: list[Any],
    label: str,
) -> list[CapabilityOptional]:

    optional: list[CapabilityOptional] = []
    for index, item in enumerate(optional_raw):
        if isinstance(item, str):
            optional.append(CapabilityOptional(name=item))
            continue
        if isinstance(item, dict):
            name = str(item.get("name", ""))
            if not name:
                raise ValueError(f"{label}[{index}].name is required")
            optional.append(
                CapabilityOptional(
                    name=name,
                    enables=str(item.get("enables", "")),
                ),
            )
            continue
        raise ValueError(f"{label}[{index}] must be a string or mapping")
    return optional


def _parse_risk_class(raw: Any, skill_id: str) -> list[str]:
    if raw is None:
        raise ValueError(f"skills.{skill_id}.risk_class is required")
    if not isinstance(raw, list) or not raw:
        raise ValueError(f"skills.{skill_id}.risk_class must be a non-empty list")
    parsed = [str(item) for item in raw]
    unknown = sorted({item for item in parsed if item not in ALLOWED_RISK_CLASSES})
    if unknown:
        raise ValueError(f"skills.{skill_id}.risk_class invalid values: {', '.join(unknown)}")
    return parsed
