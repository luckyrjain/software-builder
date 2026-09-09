"""The one place that names skills.yaml's location.

Five modules (manifest.py, capability_catalog.py, composition_runtime.py,
composition_contracts.py, canonical_manifest.py) each independently declared
`ROOT / "skills.yaml"` under a differently-named constant of their own
(CONTRACTS_PATH, SKILLS_PATH, CANONICAL_RUNTIME_PATH, CANONICAL_CONTRACTS_PATH,
CANONICAL_PATH) -- if the canonical manifest were ever renamed or relocated, every
one of those needed updating by hand, with no single symbol to change and no test
that would catch a missed one. manifest.py's and canonical_manifest.py's copies
turned out to be entirely unused (dead code, not even read within their own file)
and were deleted outright; the three still-live ones (used as each function's
default `root`-relative path) now import this instead of redeclaring it.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.registry.models import Registry, SkillEntry

ROOT = Path(__file__).resolve().parents[2]
SKILLS_YAML_PATH = ROOT / "skills.yaml"


def skill_dir(root: Path, registry: "Registry", skill_id: str) -> Path:
    """Resolve a skill's directory from the registry's declared `path:` field.

    Falls back to `root / skill_id` only if the skill has no registry entry (absent
    from `registry.skills`), matching the historical default before every skill
    fragment declared `path:` explicitly -- never raises on a missing entry, mirroring
    scripts/lint_skills.py:526-529's `entry.get("path", skill_id)` precedent (that
    function reads the *raw* `load_registry_raw` mapping; this one takes the typed
    `Registry` object `scripts.registry.schema.parse_registry`/`load_registry` return,
    since that's the shape almost every call site already has in hand after parsing
    skills.yaml once, rather than making each one re-derive a raw mapping just to call
    this).

    Once `skills/<name>` lands in every `scripts/registry/skills.d/*.yaml` fragment's
    `path:` (see the parent migration plan), every caller that resolves a skill's
    on-disk directory through this helper -- instead of assuming the directory name
    equals the registry id -- picks that up automatically, with no further code change.
    """
    entry = registry.skills.get(skill_id)
    if entry is None:
        return root / skill_id
    return root / entry.path


def skill_dir_from_entry(root: Path, entry: "SkillEntry | None", skill_id: str) -> Path:
    """Same resolution as `skill_dir`, for a caller that already holds the skill's
    `SkillEntry` -- e.g. from iterating `registry.skills.items()` -- rather than the
    registry object itself, so it doesn't have to re-look-up what it's already holding.
    `entry=None` (skill absent from the registry) falls back to `root / skill_id`, same
    as `skill_dir`.
    """
    if entry is None:
        return root / skill_id
    return root / entry.path
