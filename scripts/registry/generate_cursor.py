from __future__ import annotations

from pathlib import Path

from scripts.registry.models import Registry


def _first_line(description: str) -> str:
    return description.strip().splitlines()[0].strip()


def render_cursor_rule(skill_id: str, description: str, discovery: str) -> str:
    always_apply = "true" if discovery == "always" else "false"
    body = (
        f"Invoke the {skill_id} skill. Read `{skill_id}/SKILL.md` and follow it.\n"
        f"Phase index: `{skill_id}/reference/phase-index.md` when present under the skill directory.\n"
    )
    return (
        "---\n"
        f"description: {_first_line(description)}\n"
        f"alwaysApply: {always_apply}\n"
        "---\n\n"
        "<!-- GENERATED from skills.yaml + SKILL.md — do not edit; run make generate -->\n\n"
        f"{body}"
    )


def generate_cursor_rules(
    root: Path,
    registry: Registry,
    descriptions: dict[str, str],
) -> dict[Path, str]:
    outputs: dict[Path, str] = {}
    for skill_id, entry in sorted(registry.skills.items()):
        out_path = root / ".cursor" / "rules" / f"{skill_id}.mdc"
        outputs[out_path] = render_cursor_rule(
            skill_id,
            descriptions[skill_id],
            entry.hosts.cursor.discovery,
        )
    return outputs
