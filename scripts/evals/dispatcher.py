"""Deterministic intent dispatcher used by Batch 3 routing/scenario evals.

This is a test oracle for the repository's declared routing ownership. It is not
a replacement for host/model routing quality evals; it gives CI executable
routing behavior instead of regex-checking Markdown table consistency only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.registry.schema import Registry
from scripts.yaml_safety import load_unique_yaml_file, require_mapping


@dataclass(frozen=True)
class DispatchResult:
    status: str
    candidates: tuple[str, ...]

    @property
    def owner(self) -> str | None:
        return self.candidates[0] if self.status == "selected" and len(self.candidates) == 1 else None


@dataclass(frozen=True)
class RoutingRule:
    include: tuple[re.Pattern[str], ...]
    exclude: tuple[re.Pattern[str], ...]


def _compile_list(value: Any, label: str, *, required: bool) -> tuple[re.Pattern[str], ...]:
    if value is None and not required:
        return ()
    if not isinstance(value, list) or (required and not value) or not all(isinstance(item, str) and item for item in value):
        qualifier = "non-empty " if required else ""
        raise ValueError(f"{label} must be a {qualifier}string list")
    try:
        return tuple(re.compile(pattern, flags=re.IGNORECASE) for pattern in value)
    except re.error as exc:
        raise ValueError(f"{label}: invalid regex: {exc}") from exc


def load_routing_rules(root: Path, registry: Registry) -> dict[str, RoutingRule]:
    raw = require_mapping(
        load_unique_yaml_file(root / "scripts" / "registry" / "routing_rules.yaml"),
        "routing rules",
    )
    if raw.get("schema_version") != 1:
        raise ValueError("routing_rules.schema_version must be 1")
    routes = require_mapping(raw.get("routes"), "routing rules.routes")
    registered = set(registry.skills)
    declared = set(routes)
    if declared != registered:
        raise ValueError(
            "routing rules must cover exactly all registered skills; "
            f"missing={sorted(registered - declared)}, extra={sorted(declared - registered)}",
        )

    compiled: dict[str, RoutingRule] = {}
    for skill_id, config_raw in sorted(routes.items()):
        config = require_mapping(config_raw, f"routing rules.routes.{skill_id}")
        compiled[skill_id] = RoutingRule(
            include=_compile_list(config.get("patterns"), f"routing rules.routes.{skill_id}.patterns", required=True),
            exclude=_compile_list(
                config.get("exclude_patterns"),
                f"routing rules.routes.{skill_id}.exclude_patterns",
                required=False,
            ),
        )
    return compiled


def dispatch_with_rules(rules: dict[str, RoutingRule], prompt: str) -> DispatchResult:
    if not isinstance(prompt, str) or not prompt.strip():
        return DispatchResult("no_match", ())
    matches = tuple(
        skill_id
        for skill_id, rule in sorted(rules.items())
        if any(pattern.search(prompt) for pattern in rule.include)
        and not any(pattern.search(prompt) for pattern in rule.exclude)
    )
    if not matches:
        return DispatchResult("no_match", ())
    if len(matches) == 1:
        return DispatchResult("selected", matches)
    return DispatchResult("ambiguous", matches)


def dispatch_prompt(root: Path, registry: Registry, prompt: str) -> DispatchResult:
    return dispatch_with_rules(load_routing_rules(root, registry), prompt)


def simulate_capability_loss(registry: Registry, skill_id: str, missing: str, available: list[str]) -> str:
    """Return BLOCKED, DEGRADED, FALLBACK, or INVALID for one capability-loss scenario."""
    if skill_id not in registry.skills:
        return "INVALID"
    entry: Any = registry.skills[skill_id]
    available_set = set(available)

    if missing in set(entry.capabilities.required):
        return "BLOCKED"

    optional_names = {item.name for item in entry.capabilities.optional}
    if missing in optional_names:
        return "DEGRADED"

    affected_any_of = [path for path in entry.capabilities.any_of if missing in set(path.required)]
    if affected_any_of:
        for path in entry.capabilities.any_of:
            if missing in set(path.required):
                continue
            if set(path.required).issubset(available_set):
                return "FALLBACK"
        return "BLOCKED"

    for path in entry.capabilities.any_of:
        if missing in {item.name for item in path.optional}:
            return "DEGRADED"

    return "INVALID"
