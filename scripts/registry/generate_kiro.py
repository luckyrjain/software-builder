from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.registry.models import Registry


def render_kiro_steering(skill_id: str, discovery: str) -> str:
    inclusion = "always" if discovery == "always" else "manual"
    return (
        "---\n"
        f"inclusion: {inclusion}\n"
        "---\n\n"
        "<!-- GENERATED from skills.yaml + SKILL.md — do not edit; run make generate -->\n\n"
        f"For {skill_id}, read `{skill_id}/SKILL.md` and follow it.\n"
    )


def generate_kiro_steering(
    root: Path,
    registry: Registry,
    deprecated: dict[str, dict[str, Any]] | None = None,
) -> dict[Path, str]:
    # See generate_cursor.generate_cursor_rules: a deprecated skill's Kiro steering file is
    # equally an ambient-invocation surface (`inclusion: always`/`manual` still lets Kiro
    # bring it into context), so it is skipped here rather than (re)generated. Any copy
    # already on disk is pruned by crosscheck.find_stale_generated_adapters, which treats a
    # deprecated skill id as inactive.
    deprecated = deprecated or {}
    return {
        root / ".kiro" / "steering" / f"{skill_id}.md": render_kiro_steering(
            skill_id,
            entry.hosts["kiro"].discovery,
        )
        for skill_id, entry in sorted(registry.skills.items())
        if skill_id not in deprecated
    }
