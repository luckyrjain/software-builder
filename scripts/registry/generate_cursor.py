from __future__ import annotations

from pathlib import Path
from typing import Any

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
    deprecated: dict[str, dict[str, Any]] | None = None,
) -> dict[Path, str]:
    # A deprecated skill (docs/skill-framework/shared/deprecation-policy.md) keeps its
    # SKILL.md and stays directly invocable through its compatibility window, but its
    # Cursor rule *is* an ambient-invocation surface -- Cursor uses it to decide when to
    # bring the skill into context unprompted. Not (re)generating it here, combined with
    # crosscheck.find_stale_generated_adapters treating deprecated skills as inactive,
    # prunes any rule already on disk instead of re-emitting one every `make generate`.
    deprecated = deprecated or {}
    outputs: dict[Path, str] = {}
    for skill_id, entry in sorted(registry.skills.items()):
        if skill_id in deprecated:
            continue
        out_path = root / ".cursor" / "rules" / f"{skill_id}.mdc"
        outputs[out_path] = render_cursor_rule(
            skill_id,
            descriptions[skill_id],
            entry.hosts["cursor"].discovery,
        )
    return outputs
