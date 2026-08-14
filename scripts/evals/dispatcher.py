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


def load_routing_rules(root: Path, registry: Registry) -> dict[str, tuple[re.Pattern[str], ...]]:
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

    compiled: dict[str, tuple[re.Pattern[str], ...]] = {}
    for skill_id, config_raw in sorted(routes.items()):
        config = require_mapping(config_raw, f"routing rules.routes.{skill_id}")
        patterns = config.get("patterns")
        if not isinstance(patterns, list) or not patterns or not all(isinstance(item, str) and item for item in patterns):
            raise ValueError(f"routing rules.routes.{skill_id}.patterns must be a non-empty string list")
        try:
            compiled[skill_id] = tuple(re.compile(pattern, flags=re.IGNORECASE) for pattern in patterns)
        except re.error as exc:
            raise ValueError(f"routing rules.routes.{skill_id}: invalid regex: {exc}") from exc
    return compiled


def dispatch_prompt(root: Path, registry: Registry, prompt: str) -> DispatchResult:
    if not isinstance(prompt, str) or not prompt.strip():
        return DispatchResult("no_match", ())
    rules = load_routing_rules(root, registry)
    matches = tuple(
        skill_id
        for skill_id, patterns in sorted(rules.items())
        if any(pattern.search(prompt) for pattern in patterns)
    )
    if not matches:
        return DispatchResult("no_match", ())
    if len(matches) == 1:
        return DispatchResult("selected", matches)
    return DispatchResult("ambiguous", matches)


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
