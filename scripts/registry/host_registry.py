"""Typed parsing and fail-closed validation for agent-hosts.yaml."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, fields
from functools import cached_property
from pathlib import Path
from typing import Any

from scripts.yaml_safety import load_unique_yaml_file

ALLOWED_SCOPES = frozenset({"project", "user"})
ALLOWED_SURFACES = frozenset({"CLOUD", "LOCAL", "REMOTE", "UNKNOWN", "WEB"})
ALLOWED_DISCOVERY_MODES = frozenset({"ADAPTER", "ALIAS", "MANUAL", "NATIVE", "NONE"})
ALLOWED_CAPABILITY_STATES = frozenset({"AVAILABLE", "UNAVAILABLE", "UNKNOWN"})
ALLOWED_ISOLATION_MODES = frozenset({"NONE", "PARTIAL", "SEQUENTIAL_ONLY", "STRONG", "UNKNOWN"})
ALLOWED_VERIFICATION_STATES = frozenset({"CONFLICTED", "STALE", "UNVERIFIED", "VERIFIED"})
ALLOWED_EVIDENCE_KINDS = frozenset({"DOCUMENTATION", "REPOSITORY", "RUNTIME"})
ALLOWED_MAINTAINER_SUPPORT = frozenset(
    {"BEST_EFFORT", "COMMUNITY", "DEPRECATED", "FIRST_CLASS", "MANUAL_ONLY"}
)

_PATH_VARIABLE_RE = re.compile(r"\{([^{}]+)\}")
_SAFE_PATH_LITERAL_RE = re.compile(r"[A-Za-z0-9._/@+=,: \-]+\Z")


class HostRegistryParseError(ValueError):
    """One or more deterministic host-registry validation errors."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = sorted(set(errors))
        super().__init__("\n".join(self.errors))


@dataclass(frozen=True)
class TargetSpec:
    id: str
    scope: str
    path: str


@dataclass(frozen=True)
class DiscoveryBinding:
    target: TargetSpec
    mode: str
    precedence: int


@dataclass(frozen=True)
class SurfaceSpec:
    kind: str
    discovery: tuple[DiscoveryBinding, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CapabilitySpec:
    values: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    def state_for(self, capability: str) -> str | None:
        return self._by_name.get(capability)

    @cached_property
    def _by_name(self) -> dict[str, str]:
        return dict(self.values)

    @cached_property
    def available(self) -> frozenset[str]:
        return frozenset(name for name, state in self.values if state == "AVAILABLE")


@dataclass(frozen=True)
class IsolationSpec:
    mode: str


@dataclass(frozen=True)
class ConstraintsSpec:
    values: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class EvidenceSpec:
    kind: str
    reference: str


@dataclass(frozen=True)
class HostSpec:
    id: str
    surfaces: tuple[SurfaceSpec, ...]
    capabilities: CapabilitySpec
    isolation: IsolationSpec
    constraints: ConstraintsSpec
    verification: str
    evidence: tuple[EvidenceSpec, ...]
    maintainer_support: str


@dataclass(frozen=True)
class HostRegistry:
    schema_version: int
    targets: dict[str, TargetSpec]
    hosts: dict[str, HostSpec]
    aliases: dict[str, HostSpec]


@dataclass(frozen=True)
class _RawDiscoveryBinding:
    target_id: str
    mode: str
    precedence: int
    label: str


@dataclass(frozen=True)
class _RawSurface:
    kind: str
    discovery: tuple[_RawDiscoveryBinding, ...]


@dataclass(frozen=True)
class _RawHost:
    id: str
    surfaces: tuple[_RawSurface, ...]
    capabilities: CapabilitySpec
    isolation: IsolationSpec
    constraints: ConstraintsSpec
    verification: str
    evidence: tuple[EvidenceSpec, ...]
    maintainer_support: str


def _mapping(value: Any, label: str, errors: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        errors.append(f"{label} must be a mapping")
        return None
    return value


def _sequence(value: Any, label: str, errors: list[str]) -> list[Any] | None:
    if not isinstance(value, list):
        errors.append(f"{label} must be a list")
        return None
    return value


def _unknown_fields(
    value: dict[str, Any],
    allowed: frozenset[str],
    label: str,
    errors: list[str],
) -> None:
    for key in sorted(set(value) - allowed, key=str):
        errors.append(f"{label}.{key} is unknown")


def _required_string(value: Any, label: str, errors: list[str]) -> str | None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
        return None
    return value


def _enum(value: Any, allowed: frozenset[str], label: str, errors: list[str]) -> str | None:
    parsed = _required_string(value, label, errors)
    if parsed is not None and parsed not in allowed:
        errors.append(f"{label} unsupported: {parsed!r}")
        return None
    return parsed


def _parse_target(raw: Any, index: int, errors: list[str]) -> TargetSpec | None:
    item = _mapping(raw, f"targets[{index}]", errors)
    if item is None:
        return None
    target_id = item.get("id")
    label = f"targets.{target_id}" if isinstance(target_id, str) and target_id else f"targets[{index}]"
    _unknown_fields(item, frozenset({"id", "path", "scope"}), label, errors)
    parsed_id = _required_string(target_id, f"{label}.id", errors)
    scope = _enum(item.get("scope"), ALLOWED_SCOPES, f"{label}.scope", errors)
    path = _required_string(item.get("path"), f"{label}.path", errors)
    if path is not None:
        _validate_target_path(path, scope, f"{label}.path", errors)
    if parsed_id is None or scope is None or path is None:
        return None
    return TargetSpec(id=parsed_id, scope=scope, path=path)


def _validate_target_path(path: str, scope: str | None, label: str, errors: list[str]) -> None:
    variables = _PATH_VARIABLE_RE.findall(path)
    unknown_variables = sorted(set(variables) - {"project_root"})
    for variable in unknown_variables:
        errors.append(f"{label} contains unknown path variable {{{variable}}}")
    stripped_variables = _PATH_VARIABLE_RE.sub("", path)
    if "{" in stripped_variables or "}" in stripped_variables:
        errors.append(f"{label} contains malformed path variable")
    if ".." in path.replace("\\", "/").split("/"):
        errors.append(f"{label} must not contain '..' traversal")
    if "~" in path and (not path.startswith("~/") or path.count("~") != 1):
        errors.append(f"{label} may use '~' only once as the leading user-home variable")
    if "$" in path:
        errors.append(f"{label} must not contain shell variable or command substitution syntax")
    if "`" in path:
        errors.append(f"{label} must not contain backtick command substitution syntax")
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in path):
        errors.append(f"{label} must not contain control or NUL characters")

    if scope == "project" and path.startswith("{project_root}/"):
        literal_path = path[len("{project_root}/") :]
    elif scope == "user" and path.startswith("~/"):
        literal_path = path[2:]
    else:
        literal_path = path
    if not _SAFE_PATH_LITERAL_RE.fullmatch(literal_path):
        errors.append(f"{label} contains characters outside the safe path template grammar")

    if scope == "project":
        if variables.count("project_root") != 1 or not path.startswith("{project_root}/"):
            errors.append(f"{label} for project scope must start with {{project_root}}/")
        if "~" in path:
            errors.append(f"{label} for project scope must not use '~'")
    elif scope == "user":
        if "project_root" in variables:
            errors.append(f"{label} for user scope must not use {{project_root}}")
        if not path.startswith("~/"):
            errors.append(f"{label} for user scope must start with '~/'")


def _parse_aliases(raw: Any, errors: list[str]) -> dict[str, str]:
    if raw is None:
        return {}
    items = _sequence(raw, "aliases", errors)
    if items is None:
        return {}
    aliases: dict[str, str] = {}
    for index, raw_item in enumerate(items):
        item = _mapping(raw_item, f"aliases[{index}]", errors)
        if item is None:
            continue
        alias_id = item.get("id")
        label = f"aliases.{alias_id}" if isinstance(alias_id, str) and alias_id else f"aliases[{index}]"
        _unknown_fields(item, frozenset({"id", "target"}), label, errors)
        parsed_id = _required_string(alias_id, f"{label}.id", errors)
        target = _required_string(item.get("target"), f"{label}.target", errors)
        if parsed_id is None or target is None:
            continue
        if parsed_id in aliases:
            errors.append(f"aliases.{parsed_id}.id is duplicated")
            continue
        aliases[parsed_id] = target
    return aliases


def _parse_host(raw: Any, index: int, errors: list[str]) -> _RawHost | None:
    item = _mapping(raw, f"hosts[{index}]", errors)
    if item is None:
        return None
    host_id = item.get("id")
    label = f"hosts.{host_id}" if isinstance(host_id, str) and host_id else f"hosts[{index}]"
    _unknown_fields(
        item,
        frozenset(
            {
                "capabilities",
                "constraints",
                "evidence",
                "id",
                "isolation",
                "maintainer_support",
                "surfaces",
                "verification",
            }
        ),
        label,
        errors,
    )
    parsed_id = _required_string(host_id, f"{label}.id", errors)
    surfaces = _parse_surfaces(item.get("surfaces"), label, errors)
    capabilities = _parse_capabilities(item.get("capabilities"), label, errors)
    isolation = _parse_isolation(item.get("isolation"), label, errors)
    constraints = _parse_constraints(item.get("constraints"), label, errors)
    verification = _enum(
        item.get("verification"),
        ALLOWED_VERIFICATION_STATES,
        f"{label}.verification",
        errors,
    )
    evidence = _parse_evidence(item.get("evidence"), label, errors)
    support = _enum(
        item.get("maintainer_support"),
        ALLOWED_MAINTAINER_SUPPORT,
        f"{label}.maintainer_support",
        errors,
    )
    if verification == "VERIFIED" and not any(entry.kind == "RUNTIME" for entry in evidence):
        errors.append(f"{label}.verification VERIFIED requires RUNTIME evidence")
    if None in (parsed_id, capabilities, isolation, constraints, verification, support):
        return None
    return _RawHost(
        id=parsed_id,
        surfaces=tuple(surfaces),
        capabilities=capabilities,
        isolation=isolation,
        constraints=constraints,
        verification=verification,
        evidence=tuple(evidence),
        maintainer_support=support,
    )


def _parse_surfaces(raw: Any, host_label: str, errors: list[str]) -> list[_RawSurface]:
    items = _sequence(raw, f"{host_label}.surfaces", errors)
    if items is None:
        return []
    if not items:
        errors.append(f"{host_label}.surfaces must not be empty")
    surfaces: list[_RawSurface] = []
    seen: set[str] = set()
    for index, raw_item in enumerate(items):
        label = f"{host_label}.surfaces[{index}]"
        item = _mapping(raw_item, label, errors)
        if item is None:
            continue
        _unknown_fields(item, frozenset({"discovery", "kind"}), label, errors)
        kind = _enum(item.get("kind"), ALLOWED_SURFACES, f"{label}.kind", errors)
        discovery = _parse_discovery(item.get("discovery"), label, errors)
        if kind is None:
            continue
        if kind in seen:
            errors.append(f"{label}.kind is duplicated: {kind!r}")
            continue
        seen.add(kind)
        surfaces.append(_RawSurface(kind=kind, discovery=tuple(discovery)))
    return surfaces


def _parse_discovery(raw: Any, surface_label: str, errors: list[str]) -> list[_RawDiscoveryBinding]:
    items = _sequence(raw, f"{surface_label}.discovery", errors)
    if items is None:
        return []
    if not items:
        errors.append(f"{surface_label}.discovery must not be empty")
    bindings: list[_RawDiscoveryBinding] = []
    seen_targets: set[str] = set()
    seen_precedence: set[int] = set()
    for index, raw_item in enumerate(items):
        label = f"{surface_label}.discovery[{index}]"
        item = _mapping(raw_item, label, errors)
        if item is None:
            continue
        _unknown_fields(item, frozenset({"mode", "precedence", "target"}), label, errors)
        target = _required_string(item.get("target"), f"{label}.target", errors)
        mode = _enum(
            item.get("mode"),
            ALLOWED_DISCOVERY_MODES,
            f"{label}.mode",
            errors,
        )
        precedence = item.get("precedence")
        if isinstance(precedence, bool) or not isinstance(precedence, int) or precedence < 0:
            errors.append(f"{label}.precedence must be a non-negative integer")
            parsed_precedence = None
        else:
            parsed_precedence = precedence
        if target is not None and target in seen_targets:
            errors.append(f"{label}.target is duplicated: {target!r}")
        if parsed_precedence is not None and parsed_precedence in seen_precedence:
            errors.append(f"{label}.precedence is duplicated: {parsed_precedence}")
        if target is None or mode is None or parsed_precedence is None:
            continue
        seen_targets.add(target)
        seen_precedence.add(parsed_precedence)
        bindings.append(
            _RawDiscoveryBinding(
                target_id=target,
                mode=mode,
                precedence=parsed_precedence,
                label=label,
            )
        )
    return bindings


def _parse_capabilities(raw: Any, host_label: str, errors: list[str]) -> CapabilitySpec | None:
    values = _mapping(raw, f"{host_label}.capabilities", errors)
    if values is None:
        return None
    parsed: list[tuple[str, str]] = []
    for name in sorted(values, key=str):
        label = f"{host_label}.capabilities.{name}"
        if not isinstance(name, str) or not name:
            errors.append(f"{label} capability name must be a non-empty string")
            continue
        state = _enum(values[name], ALLOWED_CAPABILITY_STATES, label, errors)
        if state is not None:
            parsed.append((name, state))
    return CapabilitySpec(values=tuple(parsed))


def _parse_isolation(raw: Any, host_label: str, errors: list[str]) -> IsolationSpec | None:
    label = f"{host_label}.isolation"
    item = _mapping(raw, label, errors)
    if item is None:
        return None
    _unknown_fields(item, frozenset({"mode"}), label, errors)
    mode = _enum(item.get("mode"), ALLOWED_ISOLATION_MODES, f"{label}.mode", errors)
    return IsolationSpec(mode=mode) if mode is not None else None


def _parse_constraints(raw: Any, host_label: str, errors: list[str]) -> ConstraintsSpec | None:
    label = f"{host_label}.constraints"
    items = _sequence(raw, label, errors)
    if items is None:
        return None
    values: list[str] = []
    for index, item in enumerate(items):
        value = _required_string(item, f"{label}[{index}]", errors)
        if value is not None:
            values.append(value)
    return ConstraintsSpec(values=tuple(values))


def _parse_evidence(raw: Any, host_label: str, errors: list[str]) -> list[EvidenceSpec]:
    label = f"{host_label}.evidence"
    items = _sequence(raw, label, errors)
    if items is None:
        return []
    evidence: list[EvidenceSpec] = []
    for index, raw_item in enumerate(items):
        item_label = f"{label}[{index}]"
        item = _mapping(raw_item, item_label, errors)
        if item is None:
            continue
        _unknown_fields(item, frozenset({"kind", "reference"}), item_label, errors)
        kind = _enum(
            item.get("kind"),
            ALLOWED_EVIDENCE_KINDS,
            f"{item_label}.kind",
            errors,
        )
        reference = _required_string(item.get("reference"), f"{item_label}.reference", errors)
        if kind is not None and reference is not None:
            evidence.append(EvidenceSpec(kind=kind, reference=reference))
    return evidence


def _resolve_aliases(
    aliases: dict[str, str],
    hosts: dict[str, HostSpec],
    errors: list[str],
) -> dict[str, HostSpec]:
    resolved: dict[str, HostSpec] = {}
    visiting: set[str] = set()

    def resolve(alias_id: str) -> HostSpec | None:
        if alias_id in resolved:
            return resolved[alias_id]
        if alias_id in visiting:
            errors.append(f"aliases.{alias_id}.target forms an alias cycle")
            return None
        visiting.add(alias_id)
        target_id = aliases[alias_id]
        if target_id in hosts:
            host = hosts[target_id]
        elif target_id in aliases:
            host = resolve(target_id)
        else:
            errors.append(f"aliases.{alias_id}.target references unknown host or alias {target_id!r}")
            host = None
        visiting.remove(alias_id)
        if host is not None:
            resolved[alias_id] = host
        return host

    for alias_id in sorted(aliases):
        if alias_id in hosts:
            errors.append(f"aliases.{alias_id}.id collides with host id")
            continue
        resolve(alias_id)
    return resolved


def parse_host_registry(path: Path) -> HostRegistry:
    """Parse schema version 1 of the declarative agent-host registry."""
    raw = load_unique_yaml_file(path)
    errors: list[str] = []
    root = _mapping(raw, "agent-hosts.yaml", errors)
    if root is None:
        raise HostRegistryParseError(errors)
    _unknown_fields(
        root,
        frozenset({"aliases", "hosts", "schema_version", "targets"}),
        "agent-hosts.yaml",
        errors,
    )

    schema_version = root.get("schema_version")
    if isinstance(schema_version, bool) or not isinstance(schema_version, int):
        errors.append("schema_version must be integer 1")
    elif schema_version != 1:
        errors.append(f"schema_version unsupported: {schema_version!r}")

    targets: dict[str, TargetSpec] = {}
    target_items = _sequence(root.get("targets"), "targets", errors) or []
    for index, raw_target in enumerate(target_items):
        target = _parse_target(raw_target, index, errors)
        if target is None:
            continue
        if target.id in targets:
            errors.append(f"targets.{target.id}.id is duplicated")
            continue
        targets[target.id] = target

    aliases = _parse_aliases(root.get("aliases"), errors)

    raw_hosts: dict[str, _RawHost] = {}
    host_items = _sequence(root.get("hosts"), "hosts", errors) or []
    for index, raw_host in enumerate(host_items):
        host = _parse_host(raw_host, index, errors)
        if host is None:
            continue
        if host.id in raw_hosts:
            errors.append(f"hosts.{host.id}.id is duplicated")
            continue
        raw_hosts[host.id] = host

    hosts: dict[str, HostSpec] = {}
    for host_id, raw_host in sorted(raw_hosts.items()):
        surfaces: list[SurfaceSpec] = []
        for surface in raw_host.surfaces:
            discovery: list[DiscoveryBinding] = []
            for binding in surface.discovery:
                target = targets.get(binding.target_id)
                if target is None:
                    errors.append(
                        f"{binding.label}.target references unknown target {binding.target_id!r}"
                    )
                    continue
                discovery.append(
                    DiscoveryBinding(
                        target=target,
                        mode=binding.mode,
                        precedence=binding.precedence,
                    )
                )
            surfaces.append(SurfaceSpec(kind=surface.kind, discovery=tuple(discovery)))
        # Every _RawHost field except `surfaces` carries over to HostSpec unchanged;
        # only `surfaces` needs its discovery bindings' target_id resolved to a
        # TargetSpec above. Copying the rest by field name means a new scalar
        # field only has to be added to _RawHost/HostSpec, not to this loop too.
        passthrough = {
            f.name: getattr(raw_host, f.name) for f in fields(raw_host) if f.name != "surfaces"
        }
        hosts[host_id] = HostSpec(surfaces=tuple(surfaces), **passthrough)

    resolved_aliases = _resolve_aliases(aliases, hosts, errors)
    if errors:
        raise HostRegistryParseError(errors)
    return HostRegistry(
        schema_version=1,
        targets=targets,
        hosts=hosts,
        aliases=resolved_aliases,
    )
