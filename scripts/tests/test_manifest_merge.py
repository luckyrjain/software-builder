"""Tests for scripts/registry/manifest_merge.py's fragment loading and splice."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.registry.manifest_merge import (
    load_fragment_skills,
    merge_registry_yaml,
    skills_fragments_dir,
)
from scripts.registry.schema import load_registry_raw

FRAGMENT_TEMPLATE = """
{skill_id}:
  path: {skill_id}
  category: testing
  invocation: ambient
  hosts:
    cursor: {{discovery: rule}}
    claude: {{install: true}}
    kiro: {{discovery: manual}}
  install: {{requires: []}}
  capabilities:
    required: [host.repository.read]
  lint: {{skill_md_max_lines: 180, target: {skill_id}}}
  risk_class: [read-only]
"""


def _write_fragment(fragments_dir: Path, skill_id: str) -> None:
    fragments_dir.mkdir(parents=True, exist_ok=True)
    (fragments_dir / f"{skill_id}.yaml").write_text(
        FRAGMENT_TEMPLATE.format(skill_id=skill_id), encoding="utf-8"
    )


def test_load_fragment_skills_reads_every_fragment(tmp_path: Path) -> None:
    fragments_dir = skills_fragments_dir(tmp_path)
    _write_fragment(fragments_dir, "alpha")
    _write_fragment(fragments_dir, "beta")

    skills = load_fragment_skills(tmp_path)

    assert set(skills) == {"alpha", "beta"}
    assert skills["alpha"]["path"] == "alpha"


def test_load_fragment_skills_rejects_empty_fragments_dir(tmp_path: Path) -> None:
    skills_fragments_dir(tmp_path).mkdir(parents=True)

    with pytest.raises(ValueError, match="no \\*.yaml fragments"):
        load_fragment_skills(tmp_path)


def test_load_fragment_skills_rejects_filename_key_mismatch(tmp_path: Path) -> None:
    fragments_dir = skills_fragments_dir(tmp_path)
    fragments_dir.mkdir(parents=True)
    (fragments_dir / "alpha.yaml").write_text(
        FRAGMENT_TEMPLATE.format(skill_id="not-alpha"), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="must match filename"):
        load_fragment_skills(tmp_path)


def test_load_fragment_skills_rejects_multi_key_fragment(tmp_path: Path) -> None:
    fragments_dir = skills_fragments_dir(tmp_path)
    fragments_dir.mkdir(parents=True)
    (fragments_dir / "alpha.yaml").write_text(
        FRAGMENT_TEMPLATE.format(skill_id="alpha") + FRAGMENT_TEMPLATE.format(skill_id="beta"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exactly one skill entry"):
        load_fragment_skills(tmp_path)


def _write_base_skills_yaml(tmp_path: Path, body: str) -> None:
    (tmp_path / "skills.yaml").write_text(body, encoding="utf-8")


def test_merge_preserves_header_verbatim_including_comments(tmp_path: Path) -> None:
    header = (
        "schema_version: 1\n"
        "manifest_kind: canonical\n"
        "contracts:\n"
        "  # a hand-written comment a full YAML round-trip would drop\n"
        "  composition: {}\n"
        "profiles: {}\n"
    )
    _write_base_skills_yaml(tmp_path, header + "skills:\n  stale-skill:\n    path: stale-skill\n")
    _write_fragment(skills_fragments_dir(tmp_path), "fresh-skill")

    merged = merge_registry_yaml(tmp_path)

    assert merged.startswith(header)
    assert "# a hand-written comment a full YAML round-trip would drop" in merged
    parsed = yaml.safe_load(merged)
    assert set(parsed["skills"]) == {"fresh-skill"}


def test_merge_finds_real_top_level_skills_key_not_a_quoted_scalar_continuation(
    tmp_path: Path,
) -> None:
    """A quoted (not block) scalar's continuation lines are valid YAML at *any*
    indentation, including column 0 -- so a naive `^skills:` text/regex search can
    match a line that merely looks like the key inside unrelated prose. The splice
    must use the real parser's node positions instead, not text pattern matching.
    """
    base = (
        "schema_version: 1\n"
        "contracts:\n"
        "  description: \"Each entry must have a top-level\n"
        "skills:\n"
        "    key mapping skill ids to entries.\"\n"
        "skills:\n"
        "  stale-skill:\n"
        "    path: stale-skill\n"
    )
    # Confirm the fixture is itself valid, deliberately-adversarial YAML before
    # asserting anything about the merge.
    parsed_base = yaml.safe_load(base)
    assert "top-level" in parsed_base["contracts"]["description"]
    assert set(parsed_base["skills"]) == {"stale-skill"}

    _write_base_skills_yaml(tmp_path, base)
    _write_fragment(skills_fragments_dir(tmp_path), "fresh-skill")

    merged = merge_registry_yaml(tmp_path)

    # The merged document must itself be valid YAML (this is exactly what broke
    # under a naive regex splice: it spliced mid-string and produced an
    # unterminated quoted scalar).
    parsed_merged = yaml.safe_load(merged)
    assert set(parsed_merged["skills"]) == {"fresh-skill"}
    assert "top-level" in parsed_merged["contracts"]["description"]


def test_merge_raises_when_no_top_level_skills_key(tmp_path: Path) -> None:
    _write_base_skills_yaml(tmp_path, "schema_version: 1\n")
    _write_fragment(skills_fragments_dir(tmp_path), "fresh-skill")

    with pytest.raises(ValueError, match="top-level 'skills:' key"):
        merge_registry_yaml(tmp_path)


def test_load_registry_raw_prefers_fragments_over_stale_skills_yaml(tmp_path: Path) -> None:
    """Regression test for the bug this module's fragment-priority fix closed: a
    skill that exists only as a fragment (not yet merged into skills.yaml on disk)
    must still be visible to every parse_registry()/load_registry_raw() caller --
    otherwise a brand-new skill is invisible to validation until a `make generate`
    run has already happened, and an edited existing skill needs two `make generate`
    runs to converge. Deliberately does NOT add a matching skills.yaml entry for
    "fresh-skill", to prove the fragment alone is sufficient.
    """
    _write_base_skills_yaml(
        tmp_path,
        "schema_version: 1\nskills:\n  stale-skill:\n    path: stale-skill\n",
    )
    fragments_dir = skills_fragments_dir(tmp_path)
    _write_fragment(fragments_dir, "stale-skill")
    _write_fragment(fragments_dir, "fresh-skill")

    raw = load_registry_raw(tmp_path / "skills.yaml")

    assert set(raw["skills"]) == {"stale-skill", "fresh-skill"}


def test_load_registry_raw_ignores_fragments_when_directory_absent(tmp_path: Path) -> None:
    """No scripts/registry/skills.d/ directory at all -- e.g. a fork/consumer of
    this registry tooling that never adopted fragments -- must behave exactly as
    before: skills.yaml's own `skills:` mapping is authoritative as written.
    """
    _write_base_skills_yaml(
        tmp_path,
        "schema_version: 1\nskills:\n  only-skill:\n    path: only-skill\n",
    )

    raw = load_registry_raw(tmp_path / "skills.yaml")

    assert set(raw["skills"]) == {"only-skill"}
