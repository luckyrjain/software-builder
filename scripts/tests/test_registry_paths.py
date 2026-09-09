"""Tests for scripts/registry/paths.py's skill_dir()/skill_dir_from_entry() helpers.

These are the single choke point every skill-directory lookup is meant to go through
instead of assuming a skill's on-disk directory name equals its registry id (see the
module docstring and the "move skills into skills/" migration plan). Registry objects
here are built by hand (mirroring scripts/tests/test_doctor.py's _make_entry) rather
than parsed from a real skills.yaml, so these tests don't depend on -- or break when
someone edits -- the real registry contents.
"""

from __future__ import annotations

from pathlib import Path

from scripts.registry.models import InstallSpec, LintSpec, Registry, SkillEntry
from scripts.registry.paths import skill_dir, skill_dir_from_entry


def _make_entry(path: str) -> SkillEntry:
    return SkillEntry(
        path=path,
        category="test",
        invocation="ambient",
        hosts={},
        install=InstallSpec(),
        lint=LintSpec(skill_md_max_lines=180, target=path),
    )


def _make_registry(**skill_paths: str) -> Registry:
    return Registry(
        schema_version=1,
        skills={skill_id: _make_entry(path) for skill_id, path in skill_paths.items()},
    )


def test_skill_dir_resolves_through_registered_path() -> None:
    root = Path("/repo")
    registry = _make_registry(**{"pr-review": "skills/pr-review"})

    assert skill_dir(root, registry, "pr-review") == root / "skills" / "pr-review"


def test_skill_dir_path_equal_to_id_resolves_identically_to_bare_join() -> None:
    # The state every skill is in today (commit 1 is behavior-preserving): path == id,
    # so this must resolve exactly like the old `root / skill_id` it replaces.
    root = Path("/repo")
    registry = _make_registry(**{"pr-review": "pr-review"})

    assert skill_dir(root, registry, "pr-review") == root / "pr-review"


def test_skill_dir_falls_back_to_skill_id_when_unregistered() -> None:
    root = Path("/repo")
    registry = _make_registry(**{"pr-review": "pr-review"})

    assert skill_dir(root, registry, "brand-new-skill") == root / "brand-new-skill"


def test_skill_dir_falls_back_on_empty_registry() -> None:
    root = Path("/repo")
    registry = Registry(schema_version=1, skills={})

    assert skill_dir(root, registry, "solo") == root / "solo"


def test_skill_dir_from_entry_uses_the_entry_path() -> None:
    root = Path("/repo")
    entry = _make_entry("skills/pr-review")

    assert skill_dir_from_entry(root, entry, "pr-review") == root / "skills" / "pr-review"


def test_skill_dir_from_entry_falls_back_to_skill_id_when_entry_is_none() -> None:
    root = Path("/repo")

    assert skill_dir_from_entry(root, None, "pr-review") == root / "pr-review"
