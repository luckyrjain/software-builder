"""Tests for scripts/new_skill.py's scaffold() -- the "add a new skill" entry point
documented in CONTRIBUTING.md's "Registering a new skill" section and scripts/README.md.

Regression coverage for the bug the final whole-branch review of the skills/ migration
plan found: scaffold() used to place a new skill's directory and registry `path:` at
the pre-migration repo root (`<skill-id>/`) instead of under `skills/<skill-id>/`,
which broke `make validate-registry` with 42 misleading errors naming every *other*
skill rather than the actual culprit (see scripts/registry/crosscheck.py's
`_validate_skill_paths_share_one_parent`, added alongside this fix for the same
reason). There was no test file for this script before this one.
"""

from __future__ import annotations

from pathlib import Path

_EXISTING_SKILL_FRAGMENT = """existing-skill:
  path: skills/existing-skill
  category: testing
  invocation: ambient
  hosts:
    cursor: {discovery: rule}
    claude: {install: true}
    kiro: {discovery: manual}
  install:
    requires: []
  capabilities:
    required: [host.repository.read]
  lint:
    skill_md_max_lines: 180
    target: existing-skill
  risk_class: [read-only]
"""


def _write_synthetic_registry(tmp_path: Path) -> None:
    """A minimal, self-contained skills.yaml + one fragment, entirely under tmp_path --
    deliberately not the real repository's skills.yaml/skills.d/, since parsing the real
    registry pulls in agent-hosts.yaml/profiles.d cross-checks unrelated to what this
    test is verifying. Mirrors the one-skill minimal shape scripts/tests/test_registry.py
    already uses for schema-level tests (test_parse_minimal_registry).
    """
    (tmp_path / "skills.yaml").write_text("schema_version: 1\nskills: {}\n", encoding="utf-8")
    fragments_dir = tmp_path / "scripts" / "registry" / "skills.d"
    fragments_dir.mkdir(parents=True)
    (fragments_dir / "existing-skill.yaml").write_text(_EXISTING_SKILL_FRAGMENT, encoding="utf-8")


def test_scaffold_places_new_skill_under_skills_directory(tmp_path: Path) -> None:
    _write_synthetic_registry(tmp_path)

    from scripts.new_skill import scaffold

    written = scaffold("my-new-skill", "A test skill.", root=tmp_path)

    skill_md = tmp_path / "skills" / "my-new-skill" / "SKILL.md"
    assert skill_md in written
    assert skill_md.is_file()
    assert not (tmp_path / "my-new-skill").exists(), (
        "scaffold() must not also (or instead) create the skill at repo root"
    )

    fragment_path = tmp_path / "scripts" / "registry" / "skills.d" / "my-new-skill.yaml"
    assert fragment_path in written
    fragment_text = fragment_path.read_text(encoding="utf-8")
    assert "\n  path: skills/my-new-skill\n" in fragment_text


def test_scaffold_rejects_id_already_scaffolded(tmp_path: Path) -> None:
    _write_synthetic_registry(tmp_path)

    from scripts.new_skill import scaffold

    scaffold("my-new-skill", "A test skill.", root=tmp_path)

    try:
        scaffold("my-new-skill", "A test skill.", root=tmp_path)
    except FileExistsError as exc:
        assert "skills/my-new-skill" in str(exc)
    else:
        raise AssertionError("expected FileExistsError on a second scaffold of the same id")
