"""Merge per-skill authoring fragments into the generated root skills.yaml.

At 38 skills, skills.yaml is one ~4400-line hand-edited file: shared
contracts/schema at the top, then every skill's own ~50-line entry under a
single `skills:` mapping. Every skill-adding PR touches that same mapping,
which guarantees merge conflicts as the registry grows.

This module lets skills be authored one-per-file under
scripts/registry/skills.d/<skill-id>.yaml instead, and produces the merged
skills.yaml content -- mirroring the pattern generate_cursor.py/
generate_kiro.py already use for per-host adapters generated FROM the
canonical source. skills.yaml itself stays the single file every existing
consumer (validators, generators, tests, docs) reads unchanged; only its
`skills:` mapping becomes generated content, wired into cli.py's
_collect_outputs/cmd_generate the same way those adapters are.

Repos/fixtures with no scripts/registry/skills.d/ directory are untouched:
callers should only invoke merge_registry_yaml() when that directory exists,
in which case skills.yaml's own `skills:` mapping is legacy/hand-edited and
authoritative as-is (see cli.py's _collect_outputs).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

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


def _top_level_skills_key_line(text: str) -> int:
    """Return the 0-indexed source line where skills.yaml's true top-level `skills:`
    key begins, found via yaml.compose (a parse pass with no object construction)
    rather than a text/regex search.

    A regex anchored on `^skills:` looks safe -- indented block scalars can't produce
    a false match -- but a *quoted* scalar's continuation lines are valid YAML at
    *any* indentation, including column 0: `description: "...text\\nskills:\\n  more
    text..."` folds into one string, yet still contains a line that is textually
    `skills:` at the start of a line. A regex can't tell that apart from the real
    key; the parser already does, via each node's own source position.
    """
    document = yaml.compose(text)
    if not isinstance(document, yaml.MappingNode):
        raise ValueError("skills.yaml: root must be a mapping")
    for key_node, _value_node in document.value:
        if key_node.value == "skills":
            return key_node.start_mark.line
    raise ValueError("skills.yaml: expected a top-level 'skills:' key to splice fragments into")


def merge_registry_yaml(root: Path) -> str:
    """Render skills.yaml's full merged content.

    Splices a freshly-rendered `skills:` mapping (the union of scripts/registry/
    skills.d/ fragments) in place of skills.yaml's own `skills:` block via a text
    splice, not a full YAML parse+dump round-trip -- every other top-level section
    (schema_version, manifest_kind, contracts, profiles, ...) is left byte-for-byte
    untouched, comments included. Those sections stay hand-edited directly in
    skills.yaml; a full-document round-trip would silently drop any comment a
    maintainer adds there, since PyYAML's dumper has no comment-preservation.

    Only call this when scripts/registry/skills.d/ exists; see module
    docstring for why an absent fragments directory is a distinct, legacy
    code path handled by the caller instead of here.
    """
    original = (root / "skills.yaml").read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    skills_line = _top_level_skills_key_line(original)
    header = "".join(lines[:skills_line])
    rendered_skills = yaml.safe_dump(
        {"skills": load_fragment_skills(root)},
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
    )
    return header + rendered_skills
