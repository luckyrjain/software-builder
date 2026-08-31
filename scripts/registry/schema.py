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
from scripts.yaml_safety import require_mapping as _require_mapping

ALLOWED_RISK_CLASSES = frozenset(
    {"posting", "merge", "unattended", "read-only", "repository-write"},
)
AUTOMATION_ONLY_INVOCATION = "automation-only"
ALLOWED_INVOCATION = {"ambient", AUTOMATION_ONLY_INVOCATION}
ALLOWED_CURSOR_DISCOVERY = {"rule", "manual", "always"}
ALLOWED_KIRO_DISCOVERY = {"manual", "always"}
ALLOWED_COMPOSITION_MODE = {"invoke", "aggregate"}


class RegistryParseError(ValueError):
    """Raised when one or more skills in skills.yaml have invalid shape.

    Subclasses ValueError so every existing `except ValueError` /
    `except YAML_SAFETY_ERRORS` call site keeps working unchanged. Unlike a
    plain ValueError, the message lists every broken skill's problem in one
    pass instead of just the first one found, so fixing skills.yaml doesn't
    mean fix-one/rerun/fix-the-next. Each skill's own fields are still
    validated fail-fast: a skill entry stops at its first bad field and
    moves on to the next skill, rather than accumulating every field of
    every skill -- a smaller, cheaper scope than field-level accumulation
    that still closes the actual complaint (unrelated skills no longer hide
    each other's errors).
    """

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        # Every caller renders this as `f"error: {exc}"`; indent continuation
        # lines instead of leaving them bare so all N errors read as one
        # message block, not just the first with the rest looking unflagged.
        super().__init__("\n  ".join(errors))


def _coerce_int(value: Any, *, label: str) -> int:
    # bool is an int subclass and str is int()-coercible, so both need an explicit
    # type check before int() -- anything else (None, a list, a mapping) makes bare
    # int(value) raise TypeError, not ValueError, which callers here don't catch,
    # crashing with a raw traceback instead of a clean registry-parse error.
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{label} must be an integer")
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an integer") from exc


def resolve_registry_profiles(raw: Any) -> Any:
    """Merge each skill's `extends:` profile into its entry; strip `profiles`.

    Consumers that read skills.yaml's raw dict (with or without going through
    this module) should never see `extends`/`profiles` -- they see the same
    fully-inlined shape the registry had before profiles existed.
    """
    if not isinstance(raw, dict) or raw.get("profiles") is None:
        return raw
    profiles = raw["profiles"]
    if not isinstance(profiles, dict):
        raise ValueError("skills.yaml profiles must be a mapping")
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        return raw
    resolved: dict[str, Any] = {}
    for skill_id, entry in skills.items():
        if isinstance(entry, dict) and "extends" in entry:
            profile_name = entry["extends"]
            profile = profiles.get(profile_name) if isinstance(profile_name, str) else None
            if not isinstance(profile, dict):
                raise ValueError(f"skills.{skill_id}.extends: unknown profile {profile_name!r}")
            resolved[skill_id] = _deep_merge(
                profile,
                {key: value for key, value in entry.items() if key != "extends"},
            )
        else:
            resolved[skill_id] = entry
    result = dict(raw)
    result["skills"] = resolved
    del result["profiles"]
    return result


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_registry_raw(path: Path) -> Any:
    """Load skills.yaml's raw dict with `extends:` profile inheritance resolved."""
    return resolve_registry_profiles(load_unique_yaml_file(path))


def parse_registry(path: Path) -> Registry:
    raw = load_registry_raw(path)
    root = _require_mapping(raw, "skills.yaml root")
    schema_version = _coerce_int(root.get("schema_version", 0), label="schema_version")
    if schema_version != 1:
        raise ValueError(f"unsupported schema_version: {schema_version}")

    skills_raw = _require_mapping(root.get("skills"), "skills")
    skills: dict[str, SkillEntry] = {}
    errors: list[str] = []
    for skill_id, entry_raw in skills_raw.items():
        if not isinstance(skill_id, str):
            errors.append(f"skills.{skill_id!r}: skill id must be a string")
            continue
        try:
            skills[skill_id] = _parse_skill_entry(skill_id, entry_raw)
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        raise RegistryParseError(errors)
    return Registry(schema_version=schema_version, skills=skills)


def _parse_skill_entry(skill_id: str, entry_raw: Any) -> SkillEntry:
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

    return SkillEntry(
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
            skill_md_max_lines=_coerce_int(
                lint_raw.get("skill_md_max_lines", 180),
                label=f"skills.{skill_id}.lint.skill_md_max_lines",
            ),
            target=str(lint_raw.get("target", skill_id)),
        ),
        composition=composition,
        capabilities=capabilities,
        risk_class=risk_class,
    )


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
