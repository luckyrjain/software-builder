"""Load per-skill authoring fragments from scripts/registry/skills.d/.

Split out of manifest_merge.py so it has no dependency on schema.py: schema.py needs
these loader functions (to compose the raw registry before parsing it), and
manifest_merge.py needs schema.py's resolve_registry_profiles (to re-derive contract
sub-mappings from a resolved skill view). Keeping the loaders here, with only a
stdlib + yaml_safety dependency, lets both of those imports be plain module-level
imports instead of one of them needing to be deferred inside a function to dodge an
import cycle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.yaml_safety import load_unique_yaml_file, require_mapping

FRAGMENTS_DIRNAME = "skills.d"


def skills_fragments_dir(root: Path) -> Path:
    return root / "scripts" / "registry" / FRAGMENTS_DIRNAME


def load_fragment_skills(root: Path) -> dict[str, Any]:
    """Load and merge every scripts/registry/skills.d/*.yaml fragment.

    Each fragment must be a mapping with exactly one key: the skill id, whose
    value is that skill's own entry (the same shape it had inline under
    skills.yaml's `skills:` mapping, `extends:` profile references included --
    profile resolution happens later, against the merged document). The
    fragment's filename (minus `.yaml`) must match its skill id, so a
    misnamed or accidentally duplicated fragment fails loudly instead of
    silently mismatching or shadowing another skill.
    """
    fragments_dir = skills_fragments_dir(root)
    fragment_paths = sorted(fragments_dir.glob("*.yaml"))
    if not fragment_paths:
        raise ValueError(
            f"{fragments_dir}: exists but contains no *.yaml fragments -- refusing to "
            "merge an empty skill set (a bad rebase, partial checkout, or misconfigured "
            ".gitignore could produce this; if the fragments directory itself is meant "
            "to go away, remove it rather than leaving it present and empty)",
        )
    skills: dict[str, Any] = {}
    for fragment_path in fragment_paths:
        raw = require_mapping(load_unique_yaml_file(fragment_path), str(fragment_path))
        if len(raw) != 1:
            raise ValueError(
                f"{fragment_path}: fragment must contain exactly one skill entry, got {len(raw)}",
            )
        ((skill_id, entry),) = raw.items()
        if not isinstance(skill_id, str):
            raise ValueError(f"{fragment_path}: skill id must be a string")
        if skill_id != fragment_path.stem:
            raise ValueError(
                f"{fragment_path}: fragment key {skill_id!r} must match filename {fragment_path.stem!r}.yaml",
            )
        if skill_id in skills:
            raise ValueError(f"duplicate skill id across fragments: {skill_id!r}")
        skills[skill_id] = entry
    return skills
