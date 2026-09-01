"""Tests for load_registry_raw's per-root cache (scripts/registry/schema.py)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.registry import schema
from scripts.registry.manifest_merge import skills_fragments_dir
from scripts.registry.schema import clear_registry_cache, load_registry_raw


@pytest.fixture(autouse=True)
def _reset_cache():
    clear_registry_cache()
    yield
    clear_registry_cache()


def _write_skills_yaml(tmp_path: Path, skill_id: str = "solo") -> Path:
    path = tmp_path / "skills.yaml"
    path.write_text(
        f"schema_version: 1\nskills:\n  {skill_id}:\n    path: {skill_id}\n",
        encoding="utf-8",
    )
    return path


def test_second_read_does_not_touch_disk(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_skills_yaml(tmp_path)
    load_registry_raw(path)  # primes the cache

    calls = []
    real_load = schema.load_unique_yaml_file

    def spy(p):
        calls.append(p)
        return real_load(p)

    monkeypatch.setattr(schema, "load_unique_yaml_file", spy)
    load_registry_raw(path)

    assert calls == [], "second read within the same cache lifetime must not touch disk"


def test_different_roots_do_not_collide(tmp_path: Path) -> None:
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    path_a = _write_skills_yaml(root_a, skill_id="alpha")
    path_b = _write_skills_yaml(root_b, skill_id="beta")

    raw_a = load_registry_raw(path_a)
    raw_b = load_registry_raw(path_b)

    assert set(raw_a["skills"]) == {"alpha"}
    assert set(raw_b["skills"]) == {"beta"}


def test_equivalent_but_differently_constructed_paths_share_one_cache_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _write_skills_yaml(tmp_path)
    unresolved = tmp_path / "." / "skills.yaml"

    load_registry_raw(path)

    calls = []
    real_load = schema.load_unique_yaml_file

    def spy(p):
        calls.append(p)
        return real_load(p)

    monkeypatch.setattr(schema, "load_unique_yaml_file", spy)
    load_registry_raw(unresolved)

    assert calls == [], "a path resolving to the same file must hit the same cache entry"


def test_caller_mutation_does_not_corrupt_the_cache(tmp_path: Path) -> None:
    path = _write_skills_yaml(tmp_path)

    first = load_registry_raw(path)
    first["schema_version"] = 999  # mimics canonical_manifest.load_canonical_manifest's mutation
    first["skills"]["solo"]["path"] = "mutated"

    second = load_registry_raw(path)

    assert second["schema_version"] == 1
    assert second["skills"]["solo"]["path"] == "solo"


def test_clear_registry_cache_forces_a_fresh_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = _write_skills_yaml(tmp_path)
    load_registry_raw(path)

    # Simulate cli.py's flow: write new content, then invalidate before the next read.
    _write_skills_yaml(tmp_path, skill_id="renamed")
    clear_registry_cache()

    raw = load_registry_raw(path)
    assert set(raw["skills"]) == {"renamed"}


def test_different_filenames_in_the_same_directory_do_not_collide(tmp_path: Path) -> None:
    """Regression test: the cache key is (root, filename), not just root. Before this,
    two different files requested from the same directory would silently share one
    cache entry -- unreachable through any real call site (every caller passes
    root / "skills.yaml"), but a real contract violation the key alone should prevent.
    """
    skills_path = _write_skills_yaml(tmp_path, skill_id="solo")
    other_path = tmp_path / "other.yaml"
    other_path.write_text("schema_version: 1\nskills:\n  different:\n    path: different\n", encoding="utf-8")

    first = load_registry_raw(skills_path)
    second = load_registry_raw(other_path)

    assert set(first["skills"]) == {"solo"}
    assert set(second["skills"]) == {"different"}


def test_backfill_write_invalidates_the_registry_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression test: cmd_backfill's write to skills.yaml must not leave a stale
    load_registry_raw entry behind for whatever reads that path next in the same
    process. Stubs out backfill_skills_yaml_text's catalog-matching logic (already
    covered by scripts/tests/test_backfill_capabilities.py) so this test isolates
    exactly the write-then-invalidate contract cmd_backfill itself owns.
    """
    from scripts.registry import backfill_capabilities

    path = _write_skills_yaml(tmp_path, skill_id="solo")
    load_registry_raw(path)  # primes the cache with the pre-write content

    monkeypatch.setattr(
        backfill_capabilities,
        "backfill_skills_yaml_text",
        lambda text, *, overwrite, render: (
            "schema_version: 1\nskills:\n  renamed:\n    path: renamed\n",
            ["solo"],
        ),
    )

    result = backfill_capabilities.cmd_backfill(check_only=False, overwrite=False, skills_path=path)

    assert result == 0
    raw = load_registry_raw(path)
    assert set(raw["skills"]) == {"renamed"}, "stale cache entry survived cmd_backfill's write"


def test_fragments_are_still_re_merged_correctly_through_the_cache(tmp_path: Path) -> None:
    _write_skills_yaml(tmp_path)
    fragments_dir = skills_fragments_dir(tmp_path)
    fragments_dir.mkdir(parents=True)
    (fragments_dir / "fragment-skill.yaml").write_text(
        "fragment-skill:\n  path: fragment-skill\n",
        encoding="utf-8",
    )

    raw = load_registry_raw(tmp_path / "skills.yaml")

    assert set(raw["skills"]) == {"fragment-skill"}


def test_symlinked_skills_yaml_across_two_roots_does_not_cross_contaminate(
    tmp_path: Path,
) -> None:
    """Regression test: the cache is keyed on the root directory's resolved identity,
    not the skills.yaml file's resolved identity. A file-level symlink between two
    otherwise-distinct roots must not make one root's fragment-merged content leak
    into the other's read -- the cached *value* depends on skills_fragments_dir(root),
    which is a property of the root, not of wherever skills.yaml physically lives.
    """
    root_a = tmp_path / "a"
    root_b = tmp_path / "b"
    root_a.mkdir()
    root_b.mkdir()
    _write_skills_yaml(root_a, skill_id="inline-only")
    # root_b's skills.yaml is a symlink to root_a's file, but root_b has its OWN,
    # separate skills.d/ fragment root_a doesn't have.
    os.symlink(root_a / "skills.yaml", root_b / "skills.yaml")
    fragments_dir = skills_fragments_dir(root_b)
    fragments_dir.mkdir(parents=True)
    (fragments_dir / "root-b-fragment.yaml").write_text(
        "root-b-fragment:\n  path: root-b-fragment\n", encoding="utf-8"
    )

    raw_a = load_registry_raw(root_a / "skills.yaml")
    raw_b = load_registry_raw(root_b / "skills.yaml")

    assert set(raw_a["skills"]) == {"inline-only"}
    assert set(raw_b["skills"]) == {"root-b-fragment"}

    # Order matters for this bug class: re-reading root_a after root_b must still
    # see root_a's own data, not something root_b's read left behind.
    raw_a_again = load_registry_raw(root_a / "skills.yaml")
    assert set(raw_a_again["skills"]) == {"inline-only"}
