from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.yaml_safety import load_unique_frontmatter


def load_skill_frontmatter(skill_md: Path) -> dict[str, Any]:
    return load_unique_frontmatter(skill_md)
