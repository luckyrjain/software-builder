from __future__ import annotations

from pathlib import Path

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


def generate_kiro_steering(root: Path, registry: Registry) -> dict[Path, str]:
    return {
        root / ".kiro" / "steering" / f"{skill_id}.md": render_kiro_steering(
            skill_id,
            entry.hosts.kiro.discovery,
        )
        for skill_id, entry in sorted(registry.skills.items())
    }
