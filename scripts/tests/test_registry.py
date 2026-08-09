"""Tests for skills.yaml registry validation and generators."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

MINIMAL_COMPOSITION_CONTRACTS = """
artifact_types: []
write_authority_levels:
  read-only: 0
  comment: 1
  repository-write: 2
  automation-unattended: 3
skills:
  solo:
    produces: []
    consumes: []
    write_authority: read-only
"""


def _write_minimal_composition_contracts(tmp_path: Path) -> Path:
    path = tmp_path / "composition_contracts.yaml"
    path.write_text(MINIMAL_COMPOSITION_CONTRACTS, encoding="utf-8")
    return path


def test_parse_minimal_registry(tmp_path: Path) -> None:
    from scripts.registry.schema import parse_registry

    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        """
schema_version: 1
skills:
  squad-map:
    path: squad-map
    category: architecture
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
      target: squad-map
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    registry = parse_registry(registry_file)
    assert registry.schema_version == 1
    assert "squad-map" in registry.skills
    assert registry.skills["squad-map"].install.requires == []


def test_crosscheck_rejects_empty_description(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: foo\ndescription: '   '\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
skills:
  foo:
    path: foo
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
      target: foo
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    from scripts.registry.crosscheck import validate_registry

    errors = validate_registry(tmp_path)
    assert any("description must be a non-empty string" in error for error in errors)


def test_crosscheck_rejects_automation_only_with_always_discovery(tmp_path: Path) -> None:
    skill_dir = tmp_path / "bot"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: bot\ndescription: Bot skill.\ndisable-model-invocation: true\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
skills:
  bot:
    path: bot
    category: automation
    invocation: automation-only
    hosts:
      cursor: {discovery: always}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    capabilities:
      required: [host.repository.read]
    lint:
      skill_md_max_lines: 180
      target: bot
    risk_class: [unattended]
""",
        encoding="utf-8",
    )
    from scripts.registry.crosscheck import validate_registry

    errors = validate_registry(tmp_path)
    assert any("automation-only" in error and "always" in error for error in errors)


def test_generate_prunes_stale_generated_adapter(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_dir = tmp_path / "solo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: solo\ndescription: Solo skill.\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
skills:
  solo:
    path: solo
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install: {requires: []}
    capabilities:
      required: [host.repository.read]
    lint: {skill_md_max_lines: 180, target: solo}
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "badge <!-- skills-count:start -->0<!-- skills-count:end -->\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "REPOSITORY.md").write_text(
        "table\n<!-- registry-skills-table:start -->\n<!-- registry-skills-table:end -->\n",
        encoding="utf-8",
    )
    stale_rule = tmp_path / ".cursor" / "rules" / "removed-skill.mdc"
    stale_rule.parent.mkdir(parents=True)
    stale_rule.write_text(
        "<!-- GENERATED from skills.yaml + SKILL.md -->\n",
        encoding="utf-8",
    )
    (tmp_path / ".kiro" / "steering").mkdir(parents=True)

    contracts_path = _write_minimal_composition_contracts(tmp_path)
    monkeypatch.setattr("scripts.registry.composition_contracts.CONTRACTS_PATH", contracts_path)
    monkeypatch.setattr("scripts.registry.cli.ROOT", tmp_path)

    from scripts.registry.cli import cmd_generate

    assert cmd_generate(tmp_path, check_only=True) == 1
    assert stale_rule.exists()
    assert cmd_generate(tmp_path, check_only=False) == 0
    assert not stale_rule.exists()


def test_validate_returns_tooling_exit_code_for_bad_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "skills.yaml").write_text("schema_version: [", encoding="utf-8")
    monkeypatch.setattr("scripts.registry.cli.ROOT", tmp_path)

    from scripts.registry.cli import main

    assert main(["validate"]) == 2


def test_crosscheck_rejects_name_mismatch(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: not-foo\ndescription: test\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
skills:
  foo:
    path: foo
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
      target: foo
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    from scripts.registry.crosscheck import validate_registry

    errors = validate_registry(tmp_path)
    assert any("name mismatch" in error for error in errors)


def test_crosscheck_detects_install_cycle(tmp_path: Path) -> None:
    for skill_id in ("a", "b"):
        directory = tmp_path / skill_id
        directory.mkdir()
        (directory / "SKILL.md").write_text(
            f"---\nname: {skill_id}\ndescription: test\n---\n",
            encoding="utf-8",
        )
    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
skills:
  a:
    path: a
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install: {requires: [b]}
    capabilities:
      required: [host.repository.read]
    lint: {skill_md_max_lines: 180, target: a}
    risk_class: [read-only]
  b:
    path: b
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install: {requires: [a]}
    capabilities:
      required: [host.repository.read]
    lint: {skill_md_max_lines: 180, target: b}
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    from scripts.registry.crosscheck import validate_registry

    errors = validate_registry(tmp_path)
    assert any("cycle" in error for error in errors)


def test_crosscheck_rejects_missing_capabilities(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: foo\ndescription: test\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
skills:
  foo:
    path: foo
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: foo
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    from scripts.registry.crosscheck import validate_registry

    errors = validate_registry(tmp_path)
    assert any("missing capabilities block" in error for error in errors)


def test_bootstrap_registry_validates_on_real_repo() -> None:
    from scripts.registry.crosscheck import validate_registry

    errors = validate_registry(ROOT)
    assert errors == [], "\n".join(errors)


def test_render_cursor_rule_thin_wrapper() -> None:
    from scripts.registry.generate_cursor import render_cursor_rule

    text = render_cursor_rule("squad-map", "Map repos to squads.", "rule")
    assert "GENERATED from skills.yaml" in text
    assert "squad-map/SKILL.md" in text
    assert "mock" not in text.lower()
    assert "alwaysApply: false" in text
    assert text.count("\n") < 15


def test_render_kiro_steering_thin_wrapper() -> None:
    from scripts.registry.generate_kiro import render_kiro_steering

    text = render_kiro_steering("squad-map", "manual")
    assert "GENERATED from skills.yaml" in text
    assert "squad-map/SKILL.md" in text
    assert "inclusion: manual" in text


def test_render_install_mermaid_includes_edge() -> None:
    from scripts.registry.generate_docs import render_install_mermaid
    from scripts.registry.models import (
        HostClaude,
        HostCursor,
        HostKiro,
        Hosts,
        InstallSpec,
        LintSpec,
        Registry,
        SkillEntry,
    )

    registry = Registry(
        schema_version=1,
        skills={
            "child": SkillEntry(
                path="child",
                category="testing",
                invocation="ambient",
                hosts=Hosts(
                    cursor=HostCursor("rule"),
                    claude=HostClaude(True),
                    kiro=HostKiro("manual"),
                ),
                install=InstallSpec(requires=["parent"]),
                lint=LintSpec(180, "child"),
            ),
            "parent": SkillEntry(
                path="parent",
                category="testing",
                invocation="ambient",
                hosts=Hosts(
                    cursor=HostCursor("rule"),
                    claude=HostClaude(True),
                    kiro=HostKiro("manual"),
                ),
                install=InstallSpec(requires=[]),
                lint=LintSpec(180, "parent"),
            ),
        },
    )
    mermaid = render_install_mermaid(registry)
    assert "child --> parent" in mermaid


def test_generate_check_fails_when_cursor_rule_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    skill_dir = tmp_path / "solo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: solo\ndescription: Solo skill.\n---\n",
        encoding="utf-8",
    )
    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
skills:
  solo:
    path: solo
    category: testing
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install: {requires: []}
    capabilities:
      required: [host.repository.read]
    lint: {skill_md_max_lines: 180, target: solo}
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text(
        "badge <!-- skills-count:start -->0<!-- skills-count:end -->\n",
        encoding="utf-8",
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "REPOSITORY.md").write_text(
        "table\n<!-- registry-skills-table:start -->\n<!-- registry-skills-table:end -->\n",
        encoding="utf-8",
    )
    (tmp_path / ".cursor" / "rules").mkdir(parents=True)
    (tmp_path / ".kiro" / "steering").mkdir(parents=True)
    (tmp_path / ".cursor" / "rules" / "solo.mdc").write_text("stale\n", encoding="utf-8")
    (tmp_path / ".kiro" / "steering" / "solo.md").write_text("stale\n", encoding="utf-8")

    contracts_path = _write_minimal_composition_contracts(tmp_path)
    monkeypatch.setattr("scripts.registry.composition_contracts.CONTRACTS_PATH", contracts_path)
    monkeypatch.setattr("scripts.registry.cli.ROOT", tmp_path)

    from scripts.registry.cli import cmd_generate

    assert cmd_generate(tmp_path, check_only=True) == 1
    assert cmd_generate(tmp_path, check_only=False) == 0
    assert cmd_generate(tmp_path, check_only=True) == 0