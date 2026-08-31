"""Tests for skills.yaml registry validation and generators."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from scripts.registry.models import SkillEntry

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


def test_parse_provider_any_of_capability_paths(tmp_path: Path) -> None:
    from scripts.registry.schema import parse_registry

    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        """
schema_version: 1
skills:
  pr-review:
    path: pr-review
    category: review
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install:
      requires: []
    capabilities:
      required: []
      optional: []
      any_of:
        - name: GitHub read
          required: [github.get_pull_request, github.get_pull_request_files]
          optional:
            - name: github.create_issue_comment
              enables: summary posting
    lint:
      skill_md_max_lines: 180
      target: pr-review
    risk_class: [posting]
""",
        encoding="utf-8",
    )

    registry = parse_registry(registry_file)
    capabilities = registry.skills["pr-review"].capabilities
    assert capabilities.required == []
    assert len(capabilities.any_of) == 1
    assert capabilities.any_of[0].name == "GitHub read"
    assert capabilities.any_of[0].required == [
        "github.get_pull_request",
        "github.get_pull_request_files",
    ]
    assert capabilities.any_of[0].optional[0].name == "github.create_issue_comment"


def test_compatibility_generator_requires_globals_and_one_alternative(tmp_path: Path) -> None:
    from scripts.registry.generate_compatibility import render_compatibility_matrix

    (tmp_path / "skills.yaml").write_text(
        """
schema_version: 1
skills:
  demo:
    path: demo
    category: testing
    invocation: ambient
    version: legacy-extra-metadata
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    install: {requires: []}
    capabilities:
      required: [host.repository.read]
      optional: []
      any_of:
        - name: path A
          required: [provider.a.read]
        - name: path B
          required: [provider.b.read]
    lint: {skill_md_max_lines: 100, target: demo}
    risk_class: [read-only]
""",
        encoding="utf-8",
    )
    registry_dir = tmp_path / "scripts" / "registry"
    registry_dir.mkdir(parents=True)
    (registry_dir / "capability_catalog.yaml").write_text(
        """
skills:
  demo:
    required: [host.repository.read]
    optional: []
    any_of:
      - name: path A
        required: [provider.a.read]
      - name: path B
        required: [provider.b.read]
""",
        encoding="utf-8",
    )
    (registry_dir / "composition_contracts.yaml").write_text(
        """
artifact_types: []
write_authority_levels: {read-only: 0}
skills:
  demo: {produces: [], consumes: [], write_authority: read-only}
""",
        encoding="utf-8",
    )
    (tmp_path / "VERSION").write_text("0.0.0\n", encoding="utf-8")

    rendered = render_compatibility_matrix(tmp_path)

    assert (
        "host.repository.read AND \\(path A: provider.a.read OR path B: provider.b.read\\)"
        in rendered
    )
    demo_row = next(line for line in rendered.splitlines() if "| demo |" in line)
    assert "| rule | yes | unsupported | unsupported | manual | unsupported |" in demo_row


def test_compatibility_generator_rejects_malformed_canonical_manifest(tmp_path: Path) -> None:
    from scripts.registry.generate_compatibility import _load_optional_canonical_manifest

    (tmp_path / "skills.yaml").write_text(
        "schema_version: 1\nmanifest_kind: canonical\ncontracts: {}\nskills: {}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="canonical manifest missing contracts"):
        _load_optional_canonical_manifest(tmp_path)


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
        "---\nname: solo\nskill_version: 1.0\ndescription: Solo skill.\n---\n## Framework\n\nskill_result action_gates definition_of_done required_artifacts required_checks blocked_conditions partial_result_behavior runtime-contract.md\n",
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


def _skill_entry(
    *,
    requires: list[str] | None = None,
    invocation: str = "ambient",
    cursor_discovery: str = "rule",
    kiro_discovery: str = "manual",
    risk_class: list[str] | None = None,
) -> SkillEntry:
    from scripts.registry.models import (
        CompositionSpec,
        HostClaude,
        HostCursor,
        HostKiro,
        Hosts,
        InstallSpec,
        LintSpec,
        SkillEntry,
    )

    return SkillEntry(
        path="demo",
        category="testing",
        invocation=invocation,
        hosts=Hosts(
            cursor=HostCursor(discovery=cursor_discovery),
            claude=HostClaude(),
            kiro=HostKiro(discovery=kiro_discovery),
        ),
        install=InstallSpec(requires=requires or []),
        lint=LintSpec(skill_md_max_lines=180, target="demo"),
        composition=CompositionSpec(),
        risk_class=risk_class or [],
    )


def test_validate_install_graph_detects_cycle() -> None:
    from scripts.registry.crosscheck import _validate_install_graph
    from scripts.registry.models import Registry

    registry = Registry(
        schema_version=1,
        skills={"a": _skill_entry(requires=["b"]), "b": _skill_entry(requires=["a"])},
    )
    errors = _validate_install_graph(registry)
    assert any("cycle" in error for error in errors)


def test_validate_install_graph_rejects_unknown_dependency() -> None:
    from scripts.registry.crosscheck import _validate_install_graph
    from scripts.registry.models import Registry

    registry = Registry(schema_version=1, skills={"a": _skill_entry(requires=["ghost"])})
    errors = _validate_install_graph(registry)
    assert errors == ["error: a: install.requires unknown skill 'ghost'"]


def test_validate_install_graph_accepts_acyclic_graph() -> None:
    from scripts.registry.crosscheck import _validate_install_graph
    from scripts.registry.models import Registry

    registry = Registry(
        schema_version=1,
        skills={"a": _skill_entry(requires=["b"]), "b": _skill_entry()},
    )
    assert _validate_install_graph(registry) == []


def test_validate_install_graph_detects_self_cycle() -> None:
    from scripts.registry.crosscheck import _validate_install_graph
    from scripts.registry.models import Registry

    registry = Registry(schema_version=1, skills={"a": _skill_entry(requires=["a"])})
    errors = _validate_install_graph(registry)
    assert any("cycle" in error for error in errors)


def test_validate_automation_only_rules_accepts_compliant_skill() -> None:
    from scripts.registry.crosscheck import _validate_automation_only_rules
    from scripts.registry.models import Registry

    registry = Registry(
        schema_version=1,
        skills={
            "a": _skill_entry(
                invocation="automation-only",
                cursor_discovery="manual",
                kiro_discovery="manual",
                risk_class=["unattended"],
            ),
        },
    )
    assert _validate_automation_only_rules(registry) == []


def test_validate_automation_only_rules_rejects_always_discovery() -> None:
    from scripts.registry.crosscheck import _validate_automation_only_rules
    from scripts.registry.models import Registry

    registry = Registry(
        schema_version=1,
        skills={
            "a": _skill_entry(
                invocation="automation-only",
                cursor_discovery="always",
                risk_class=["unattended"],
            ),
            "b": _skill_entry(
                invocation="automation-only",
                kiro_discovery="always",
                risk_class=["unattended"],
            ),
        },
    )
    errors = _validate_automation_only_rules(registry)
    assert any("a: automation-only skills cannot use cursor discovery always" in e for e in errors)
    assert any("b: automation-only skills cannot use kiro discovery always" in e for e in errors)


def test_validate_automation_only_rules_requires_unattended_risk_class() -> None:
    from scripts.registry.crosscheck import _validate_automation_only_rules
    from scripts.registry.models import Registry

    registry = Registry(
        schema_version=1,
        skills={"a": _skill_entry(invocation="automation-only")},
    )
    errors = _validate_automation_only_rules(registry)
    assert any("automation-only skills must declare risk_class unattended" in e for e in errors)


def test_validate_automation_only_rules_skips_non_automation_only_skills() -> None:
    from scripts.registry.crosscheck import _validate_automation_only_rules
    from scripts.registry.models import Registry

    # Would fail every rule above if evaluated -- must be skipped entirely
    # because invocation isn't automation-only.
    registry = Registry(
        schema_version=1,
        skills={"a": _skill_entry(invocation="ambient", cursor_discovery="always")},
    )
    assert _validate_automation_only_rules(registry) == []


def test_validate_skill_directory_sync_detects_orphan_and_missing(tmp_path: Path) -> None:
    from scripts.registry.crosscheck import _validate_skill_directory_sync
    from scripts.registry.models import Registry

    orphan_dir = tmp_path / "orphan"
    orphan_dir.mkdir()
    (orphan_dir / "SKILL.md").write_text("---\nname: orphan\ndescription: test\n---\n", encoding="utf-8")

    registry = Registry(schema_version=1, skills={"missing-dir": _skill_entry()})
    errors = _validate_skill_directory_sync(tmp_path, registry)

    assert "error: orphan: directory has SKILL.md but no registry entry" in errors
    assert "error: missing-dir: registry entry has no SKILL.md directory" in errors


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


def test_update_readme_badge_keeps_markers_outside_the_image_url() -> None:
    # Regression test: the generated count previously sat *inside* the badge's image destination
    # (`...skills-<!-- skills-count:start -->23<!-- skills-count:end -->-blue)`). CommonMark's
    # grammar for a bare link/image destination forbids literal whitespace, and the marker
    # comments' own spaces broke it outright, corrupting the whole `![alt](url)` into broken
    # literal text plus a stray auto-link on the real rendered page. The image markdown must come
    # out fully intact, with the markers only ever adjacent to it on their own lines, never
    # interleaved into the URL itself.
    from scripts.registry.generate_docs import (
        README_COUNT_END,
        README_COUNT_START,
        update_readme_badge,
    )

    readme = f"# repo\n\n{README_COUNT_START}old{README_COUNT_END}\n\nmore text\n"
    updated = update_readme_badge(readme, 23)

    assert "![Skills](https://img.shields.io/badge/skills-23-blue)" in updated
    # the count must not be reachable from inside the parenthesized URL segment
    url_segment = updated.split("(", 1)[1].split(")", 1)[0]
    assert README_COUNT_START not in url_segment
    assert README_COUNT_END not in url_segment
    assert "more text" in updated  # content outside the marker block is untouched


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
        "---\nname: solo\nskill_version: 1.0\ndescription: Solo skill.\n---\n## Framework\n\nskill_result action_gates definition_of_done required_artifacts required_checks blocked_conditions partial_result_behavior runtime-contract.md\n",
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


def _skill_block(name: str, *, invocation: str = "ambient", cursor_discovery: str = "rule") -> str:
    return f"""
  {name}:
    path: {name}
    category: architecture
    invocation: {invocation}
    hosts:
      cursor: {{discovery: {cursor_discovery}}}
      claude: {{install: true}}
      kiro: {{discovery: manual}}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: {name}
    risk_class: [read-only]
"""


def test_parse_registry_reports_every_broken_skill_in_one_pass(tmp_path: Path) -> None:
    from scripts.registry.schema import RegistryParseError, parse_registry

    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        "schema_version: 1\nskills:\n"
        + _skill_block("broken-a", invocation="nonsense")
        + _skill_block("broken-b", cursor_discovery="totally-wrong")
        + _skill_block("fine-one"),
        encoding="utf-8",
    )

    with pytest.raises(RegistryParseError) as excinfo:
        parse_registry(registry_file)

    assert len(excinfo.value.errors) == 2
    assert "skills.broken-a.invocation invalid: 'nonsense'" in excinfo.value.errors[0]
    assert "skills.broken-b.hosts.cursor.discovery invalid: 'totally-wrong'" in excinfo.value.errors[1]
    # subclasses ValueError -- existing `except ValueError` call sites still catch it
    assert isinstance(excinfo.value, ValueError)


def test_parse_registry_single_broken_skill_message_is_unchanged(tmp_path: Path) -> None:
    # A single skill with a single bad field should read exactly like the old
    # fail-fast ValueError -- no behavior change for the common case.
    from scripts.registry.schema import parse_registry

    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        "schema_version: 1\nskills:\n" + _skill_block("broken-a", invocation="nonsense"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"^skills\.broken-a\.invocation invalid: 'nonsense'$"):
        parse_registry(registry_file)


def test_parse_registry_stops_at_first_bad_field_within_one_skill(tmp_path: Path) -> None:
    # Within a single skill, fields are still validated fail-fast: a skill
    # with two independent bad fields (invocation, then cursor discovery)
    # only ever surfaces the first one -- accumulation happens ACROSS
    # skills, not across a skill's own fields. See RegistryParseError's
    # docstring for why.
    from scripts.registry.schema import RegistryParseError, parse_registry

    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        "schema_version: 1\nskills:\n"
        + _skill_block("broken-both", invocation="nonsense", cursor_discovery="also-wrong"),
        encoding="utf-8",
    )

    with pytest.raises(RegistryParseError) as excinfo:
        parse_registry(registry_file)

    assert len(excinfo.value.errors) == 1
    assert "skills.broken-both.invocation invalid: 'nonsense'" in excinfo.value.errors[0]
    assert "cursor.discovery" not in excinfo.value.errors[0]


def _one_skill_registry() -> "Registry":
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

    return Registry(
        schema_version=1,
        skills={
            "pr-review": SkillEntry(
                path="pr-review",
                category="review",
                invocation="ambient",
                hosts=Hosts(
                    cursor=HostCursor("rule"),
                    claude=HostClaude(True),
                    kiro=HostKiro("manual"),
                ),
                install=InstallSpec(requires=[]),
                lint=LintSpec(180, "pr-review"),
            ),
        },
    )


def test_render_doc_links_table_links_all_three_files() -> None:
    from scripts.registry.generate_docs import render_doc_links_table

    table = render_doc_links_table(_one_skill_registry())

    assert "| **pr-review** |" in table
    assert "[pr-review/README.md](../pr-review/README.md)" in table
    assert "[pr-review/SKILL.md](../pr-review/SKILL.md)" in table
    assert "[pr-review/SETUP.md](../pr-review/SETUP.md)" in table


def test_update_readme_doc_links_replaces_marker_block_only() -> None:
    from scripts.registry.generate_docs import (
        README_LINKS_END,
        README_LINKS_START,
        update_readme_doc_links,
    )

    readme = f"intro\n\n{README_LINKS_START}\nstale\n{README_LINKS_END}\n\noutro\n"
    updated = update_readme_doc_links(readme, _one_skill_registry())

    assert "stale" not in updated
    assert "pr-review" in updated
    assert "intro" in updated and "outro" in updated


_ESCALATION_MATRIX_MD = """# Cross-skill escalation (shared)

## 1. Symmetric matrix (forward escalations)

| Trigger | From → To | Handoff artifact | User prompt template |
|---------|-----------|------------------|----------------------|
| Critical security finding | pr-review → incident-rca | MR link | "RCA for..." |
| Deploy regression confirmed | incident-rca → pr-review | MR URL | "Review MR..." |

## 2. Reverse escalations

| After skill completes | Next action | User prompt template |
|-----------------------|-------------|----------------------|
| k8s recommends Ready cut applied | Re-run k8s in **7d** | "Re-run..." |
"""


def test_parse_forward_escalation_matrix_extracts_edges() -> None:
    from scripts.registry.cross_skill_routing import parse_forward_escalation_matrix

    edges = parse_forward_escalation_matrix(_ESCALATION_MATRIX_MD)

    assert edges == [
        ("Critical security finding", "pr-review", "incident-rca"),
        ("Deploy regression confirmed", "incident-rca", "pr-review"),
    ]


def test_parse_forward_escalation_matrix_ignores_other_sections() -> None:
    # Section 2's table has no arrow at all and a different header shape — the parser must
    # stop at the next "## " heading rather than reading past it.
    from scripts.registry.cross_skill_routing import parse_forward_escalation_matrix

    edges = parse_forward_escalation_matrix(_ESCALATION_MATRIX_MD)

    assert all("k8s recommends" not in trigger for trigger, _, _ in edges)


def test_parse_forward_escalation_matrix_fails_loudly_on_missing_heading() -> None:
    from scripts.registry.cross_skill_routing import parse_forward_escalation_matrix

    with pytest.raises(ValueError, match="missing section heading"):
        parse_forward_escalation_matrix("# no matrix section here\n")


def test_parse_forward_escalation_matrix_fails_loudly_on_bad_arrow_count() -> None:
    from scripts.registry.cross_skill_routing import parse_forward_escalation_matrix

    broken = """## 1. Symmetric matrix (forward escalations)

| Trigger | From → To | Handoff artifact | User prompt template |
|---------|-----------|------------------|----------------------|
| Some trigger | pr-review incident-rca | MR link | "RCA for..." |
"""
    with pytest.raises(ValueError, match="exactly one"):
        parse_forward_escalation_matrix(broken)


def test_parse_forward_escalation_matrix_reanchors_relative_links_in_trigger() -> None:
    # Regression test: cross-skill-escalation.md lives 3 directories deep, so its relative
    # links (e.g. "../../../who-owns-x-bot/...") are anchored there. Copied verbatim into
    # docs/README.md (1 directory deep), the same link would resolve outside the repo entirely.
    from scripts.registry.cross_skill_routing import parse_forward_escalation_matrix

    markdown = """## 1. Symmetric matrix (forward escalations)

| Trigger | From → To | Handoff artifact | User prompt template |
|---------|-----------|------------------|----------------------|
| See [detail](../../../who-owns-x-bot/reference/slack-format.md#anchor) for exact wording | who-owns-x-bot → incident-rca | Service name | "RCA for..." |
"""
    edges = parse_forward_escalation_matrix(markdown)

    trigger, _source, _target = edges[0]
    assert "(../who-owns-x-bot/reference/slack-format.md#anchor)" in trigger
    assert "../../../" not in trigger


def test_update_readme_routing_table_renders_trimmed_columns() -> None:
    from scripts.registry.generate_docs import (
        README_ROUTING_END,
        README_ROUTING_START,
        update_readme_routing_table,
    )

    readme = f"intro\n\n{README_ROUTING_START}\nstale\n{README_ROUTING_END}\n\noutro\n"
    updated = update_readme_routing_table(readme, _ESCALATION_MATRIX_MD)

    assert "stale" not in updated
    assert "| pr-review | Critical security finding | incident-rca |" in updated
    # trimmed shape: no handoff-artifact/prompt-template columns from the source table
    assert "Handoff artifact" not in updated
    assert "MR link" not in updated
