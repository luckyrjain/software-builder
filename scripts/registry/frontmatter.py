from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def load_skill_frontmatter(skill_md: Path) -> dict[str, Any]:
    text = skill_md.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"missing YAML frontmatter: {skill_md}")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError(f"frontmatter must be a mapping: {skill_md}")
    return data


def automation_only_guard_errors(invocation: str, frontmatter: dict[str, Any]) -> list[str]:
    """Check SKILL.md's disable-model-invocation agrees with skills.yaml's invocation.

    Both directions: an automation-only skill must set disable-model-invocation,
    and setting disable-model-invocation implies the skill must be automation-only.
    """
    disable = frontmatter.get("disable-model-invocation") is True
    automation_only = invocation == "automation-only"
    if disable == automation_only:
        return []
    return [f"disable-model-invocation={disable} but invocation={invocation!r}"]
