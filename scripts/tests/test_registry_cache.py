"""Tests for load_registry_raw's per-root cache (scripts/registry/schema.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.registry import schema
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


def test_fragments_are_still_re_merged_correctly_through_the_cache(tmp_path: Path) -> None:
    from scripts.registry.manifest_merge import skills_fragments_dir

    _write_skills_yaml(tmp_path)
    fragments_dir = skills_fragments_dir(tmp_path)
    fragments_dir.mkdir(parents=True)
    (fragments_dir / "fragment-skill.yaml").write_text(
        "fragment-skill:\n  path: fragment-skill\n",
        encoding="utf-8",
    )

    raw = load_registry_raw(tmp_path / "skills.yaml")

    assert set(raw["skills"]) == {"fragment-skill"}
