from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from scripts.registry.models import (
    HostClaude,
    HostCursor,
    HostKiro,
    Hosts,
    InstallSpec,
    LintSpec,
    Registry,
    SkillEntry,
)

ALLOWED_INVOCATION = {"ambient", "automation-only"}
ALLOWED_CURSOR_DISCOVERY = {"rule", "manual", "always"}
ALLOWED_KIRO_DISCOVERY = {"manual", "always"}


def _require_mapping(data: Any, label: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError(f"{label} must be a mapping")
    return data


def parse_registry(path: Path) -> Registry:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
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
        )
    return Registry(schema_version=schema_version, skills=skills)
