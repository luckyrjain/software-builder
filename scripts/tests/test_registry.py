"""Tests for skills.yaml registry validation and generators."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from scripts.registry.models import Registry, SkillEntry

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


def test_crosscheck_rejects_description_missing_keywords(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: foo\ndescription: Use for foo things, not bar things.\n---\n",
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
    assert any("missing 'Keywords:'" in error for error in errors)


def test_crosscheck_accepts_description_with_keywords(tmp_path: Path) -> None:
    skill_dir = tmp_path / "foo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: foo\ndescription: >-\n  Keywords: foo things, not bar things.\n---\n",
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
    assert not any("Keywords" in error for error in errors)


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
        "---\nname: solo\nskill_version: 1.0\ndescription: 'Keywords: solo skill.'\n---\n## Framework\n\nskill_result action_gates definition_of_done required_artifacts required_checks blocked_conditions partial_result_behavior runtime-contract.md\n",
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


def test_generate_does_not_prune_stale_adapters_when_an_unrelated_error_also_fails_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # cmd_generate used to prune stale adapters *before* running validation, so a real,
    # unrelated validation failure (composition.escalation_targets here) still left the
    # stale adapter file deleted even though the run reported failure -- a "failed" run
    # that wasn't actually a no-op. Pin that a stale adapter now survives an unrelated
    # validation failure: only a run that's clean of every OTHER error may prune.
    skill_dir = tmp_path / "solo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: solo\nskill_version: 1.0\ndescription: 'Keywords: solo skill.'\n---\n## Framework\n\nskill_result action_gates definition_of_done required_artifacts required_checks blocked_conditions partial_result_behavior runtime-contract.md\n",
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
    composition:
      escalation_targets: [does-not-exist]
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

    assert cmd_generate(tmp_path, check_only=False) == 1
    assert stale_rule.exists()


def _write_minimal_registry_fixture(tmp_path: Path) -> None:
    skill_dir = tmp_path / "solo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\nname: solo\nskill_version: 1.0\ndescription: 'Keywords: solo skill.'\n---\n## Framework\n\nskill_result action_gates definition_of_done required_artifacts required_checks blocked_conditions partial_result_behavior runtime-contract.md\n",
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
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "docs" / "REPOSITORY.md").write_text(
        "table\n<!-- registry-skills-table:start -->\n<!-- registry-skills-table:end -->\n",
        encoding="utf-8",
    )
    (tmp_path / ".cursor" / "rules").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kiro" / "steering").mkdir(parents=True, exist_ok=True)


def test_cmd_generate_populates_docs_readme_link_table(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Regression test: generators.py only gates docs/README.md generation on the
    # file *existing* (`.is_file()`), not on it already containing the marker blocks -- a fixture
    # without them must fail loudly (via update_marker_block's own check), not crash uncaught.
    _write_minimal_registry_fixture(tmp_path)
    (tmp_path / "docs" / "README.md").write_text(
        "intro\n<!-- skill-doc-links:start -->\n<!-- skill-doc-links:end -->\n",
        encoding="utf-8",
    )
    contracts_path = _write_minimal_composition_contracts(tmp_path)
    monkeypatch.setattr("scripts.registry.composition_contracts.CONTRACTS_PATH", contracts_path)
    monkeypatch.setattr("scripts.registry.cli.ROOT", tmp_path)

    from scripts.registry.cli import cmd_generate

    assert cmd_generate(tmp_path, check_only=False) == 0
    docs_readme = (tmp_path / "docs" / "README.md").read_text(encoding="utf-8")
    # Exact row, not just "solo" in docs_readme -- a mutation that broke the link paths, column
    # order, or file extensions would still leave "solo" present and pass a looser assertion.
    assert (
        "| **solo** | [solo/README.md](../solo/README.md) | [solo/SKILL.md](../solo/SKILL.md) | "
        "[solo/SETUP.md](../solo/SETUP.md) |"
    ) in docs_readme
    assert cmd_generate(tmp_path, check_only=True) == 0


def test_cmd_generate_populates_docs_readme_routing_table_when_escalation_matrix_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_minimal_registry_fixture(tmp_path)
    (tmp_path / "docs" / "README.md").write_text(
        "intro\n"
        "<!-- skill-doc-links:start -->\n<!-- skill-doc-links:end -->\n"
        "<!-- cross-skill-routing:start -->\n<!-- cross-skill-routing:end -->\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "skill-framework" / "shared").mkdir(parents=True)
    (tmp_path / "docs" / "skill-framework" / "shared" / "cross-skill-escalation.md").write_text(
        "## 1. Symmetric matrix (forward escalations)\n\n"
        "| Trigger | From → To | Handoff artifact | User prompt template |\n"
        "|---------|-----------|------------------|----------------------|\n"
        "| A thing happens | solo → solo | n/a | \"...\" |\n",
        encoding="utf-8",
    )
    contracts_path = _write_minimal_composition_contracts(tmp_path)
    monkeypatch.setattr("scripts.registry.composition_contracts.CONTRACTS_PATH", contracts_path)
    monkeypatch.setattr("scripts.registry.cli.ROOT", tmp_path)

    from scripts.registry.cli import cmd_generate

    assert cmd_generate(tmp_path, check_only=False) == 0
    docs_readme = (tmp_path / "docs" / "README.md").read_text(encoding="utf-8")
    assert "| solo | A thing happens | solo |" in docs_readme
    assert cmd_generate(tmp_path, check_only=True) == 0


def test_validate_returns_tooling_exit_code_for_bad_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "skills.yaml").write_text("schema_version: [", encoding="utf-8")
    monkeypatch.setattr("scripts.registry.cli.ROOT", tmp_path)

    from scripts.registry.cli import main

    assert main(["validate"]) == 2


def test_backfill_capabilities_returns_tooling_exit_code_for_bad_yaml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    # backfill-capabilities used to bypass _run_command's uniform error handling and let a
    # malformed skills.yaml raise an unhandled exception instead of the clean `error:`/exit-2
    # contract every other subcommand gives Makefile/CI callers -- pin that it's wrapped now.
    (tmp_path / "skills.yaml").write_text("schema_version: [", encoding="utf-8")
    monkeypatch.setattr("scripts.registry.cli.ROOT", tmp_path)

    from scripts.registry.cli import main

    assert main(["backfill-capabilities"]) == 2


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
        HostDiscoverySpec,
        InstallSpec,
        LintSpec,
        SkillEntry,
    )

    return SkillEntry(
        path="demo",
        category="testing",
        invocation=invocation,
        hosts={
            "cursor": HostDiscoverySpec(discovery=cursor_discovery),
            "claude": HostDiscoverySpec(install=True),
            "kiro": HostDiscoverySpec(discovery=kiro_discovery),
        },
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


def test_update_marker_block_does_not_interpret_backreferences_in_content() -> None:
    # Regression test: re.sub treats a *string* repl's backslash-escapes (\g<0>, \1, ...) as
    # backreferences. update_marker_block's content can be free-text prose copied out of a repo
    # markdown file (a cross-skill-escalation.md Trigger cell), not just controlled registry
    # strings, so a stray "\g<0>" in that prose must not silently splice the old block content
    # back into the new one.
    from scripts.registry.generate_docs import update_marker_block

    text = "before\n<!-- x:start -->OLD<!-- x:end -->\nafter"
    content = "contains a backslash trick: \\g<0> and \\1 here"

    updated = update_marker_block(text, "<!-- x:start -->", "<!-- x:end -->", content)

    assert updated == f"before\n<!-- x:start -->{content}<!-- x:end -->\nafter"
    assert "OLD" not in updated


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
        HostDiscoverySpec,
        InstallSpec,
        LintSpec,
        Registry,
        SkillEntry,
    )

    minimal_hosts = {
        "cursor": HostDiscoverySpec(discovery="rule"),
        "claude": HostDiscoverySpec(install=True),
        "kiro": HostDiscoverySpec(discovery="manual"),
    }
    registry = Registry(
        schema_version=1,
        skills={
            "child": SkillEntry(
                path="child",
                category="testing",
                invocation="ambient",
                hosts=minimal_hosts,
                install=InstallSpec(requires=["parent"]),
                lint=LintSpec(180, "child"),
            ),
            "parent": SkillEntry(
                path="parent",
                category="testing",
                invocation="ambient",
                hosts=minimal_hosts,
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
        "---\nname: solo\nskill_version: 1.0\ndescription: 'Keywords: solo skill.'\n---\n## Framework\n\nskill_result action_gates definition_of_done required_artifacts required_checks blocked_conditions partial_result_behavior runtime-contract.md\n",
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
        HostDiscoverySpec,
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
                hosts={
                    "cursor": HostDiscoverySpec(discovery="rule"),
                    "claude": HostDiscoverySpec(install=True),
                    "kiro": HostDiscoverySpec(discovery="manual"),
                },
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


def test_markdown_link_regex_captures_full_target_with_nested_parens() -> None:
    # Regression test: a naive "[^)]+"/"[^)\s]+" target class truncates at the FIRST ")", which
    # corrupts any link whose target legitimately contains one (e.g. a Wikipedia-style URL ending
    # in "_(bar)"). Asserts on the regex's own capture group directly rather than end-to-end
    # through reanchor_relative_links() -- for an http(s) target specifically, _reanchor_link_target
    # returns whatever it's given unchanged, and the leftover unmatched text after a truncated
    # match happens to recombine into the original string either way, masking the bug end-to-end.
    from scripts.registry.cross_skill_routing import _MARKDOWN_LINK

    match = _MARKDOWN_LINK.search("[wiki](https://en.wikipedia.org/wiki/Foo_(bar))")

    assert match is not None
    assert match.group(2) == "https://en.wikipedia.org/wiki/Foo_(bar)"


def test_reanchor_relative_links_preserves_parens_in_relative_link_target() -> None:
    # End-to-end version of the regression above. Many inputs with parens don't actually
    # discriminate old vs. new regex behavior here: a truncated target's dropped suffix often
    # reappends as untouched leftover text and coincidentally reconstructs the same final string.
    # This input does discriminate: the truncated old capture drops a trailing "/../other.md"
    # segment from what posixpath.normpath sees, leaving an un-collapsed ".." in the output
    # instead of correctly resolving to "other.md".
    from scripts.registry.cross_skill_routing import reanchor_relative_links

    text = "See [x](../shared/foo_(bar)/../other.md) end"

    result = reanchor_relative_links(text)

    assert result == "See [x](skill-framework/shared/other.md) end"


def test_reanchor_relative_links_leaves_absolute_paths_unchanged() -> None:
    # Regression test: an absolute-path target isn't anchored to _SOURCE_DIR, and rewriting it
    # via posixpath.relpath against the relative _DEST_DIR would resolve against the invoking
    # process's actual cwd -- producing output that depends on where `make generate` is run from,
    # not just file content. No such link exists in cross-skill-escalation.md today; this guards
    # against one being added later.
    from scripts.registry.cross_skill_routing import reanchor_relative_links

    text = "See [x](/some/absolute/path.md) for detail"

    result = reanchor_relative_links(text)

    assert result == text


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


def test_parse_registry_resolves_extends_profile(tmp_path: Path) -> None:
    from scripts.registry.schema import parse_registry

    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        """
schema_version: 1
profiles:
  read-only-leaf-review:
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    risk_class: [read-only]
skills:
  squad-map:
    path: squad-map
    category: architecture
    extends: read-only-leaf-review
    install:
      requires: []
    capabilities:
      required: [host.repository.read]
    lint:
      skill_md_max_lines: 180
      target: squad-map
""",
        encoding="utf-8",
    )

    registry = parse_registry(registry_file)
    entry = registry.skills["squad-map"]
    assert entry.invocation == "ambient"
    assert entry.hosts["cursor"].discovery == "rule"
    assert entry.risk_class == ["read-only"]
    assert entry.install.requires == []


def test_parse_registry_extends_unknown_profile_raises(tmp_path: Path) -> None:
    from scripts.registry.schema import parse_registry

    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        """
schema_version: 1
profiles:
  read-only-leaf-review:
    invocation: ambient
skills:
  squad-map:
    path: squad-map
    category: architecture
    extends: nonexistent-profile
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: squad-map
    risk_class: [read-only]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"skills\.squad-map\.extends: unknown profile 'nonexistent-profile'"):
        parse_registry(registry_file)


def test_parse_registry_skill_field_overrides_profile_field(tmp_path: Path) -> None:
    # Deep merge, not full replace: a skill overriding one nested hosts.*
    # field keeps the rest of the profile's hosts block.
    from scripts.registry.schema import parse_registry

    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
        """
schema_version: 1
profiles:
  read-only-leaf-review:
    invocation: ambient
    hosts:
      cursor: {discovery: rule}
      claude: {install: true}
      kiro: {discovery: manual}
    risk_class: [read-only]
skills:
  squad-map:
    path: squad-map
    category: architecture
    extends: read-only-leaf-review
    hosts:
      cursor: {discovery: always}
    install:
      requires: []
    lint:
      skill_md_max_lines: 180
      target: squad-map
""",
        encoding="utf-8",
    )

    registry = parse_registry(registry_file)
    entry = registry.skills["squad-map"]
    assert entry.hosts["cursor"].discovery == "always"
    assert entry.hosts["claude"].install is True
    assert entry.hosts["kiro"].discovery == "manual"


def test_resolve_registry_profiles_noop_without_profiles_key() -> None:
    from scripts.registry.schema import resolve_registry_profiles

    raw = {
        "schema_version": 1,
        "skills": {"squad-map": {"path": "squad-map", "invocation": "ambient"}},
    }
    assert resolve_registry_profiles(raw) is raw


def test_parse_changelog_sections_lists_headings_in_order_and_skips_fenced_code() -> None:
    from scripts.registry.generate_docs import parse_changelog_sections

    changelog = """# Changelog

## Platform

### An entry (2026-01-01)

```
## not a real heading, inside a fence
```

- bullet

## squad-map

### Another entry (2026-01-02)

- bullet

## Platform
"""
    assert parse_changelog_sections(changelog) == ["Platform", "squad-map", "Platform"]


def test_render_changelog_toc_disambiguates_repeated_section_names() -> None:
    from scripts.registry.generate_docs import render_changelog_toc

    toc = render_changelog_toc(["Platform", "squad-map", "Platform"])

    assert toc == (
        "- [Platform](#platform)\n"
        "- [squad-map](#squad-map)\n"
        "- [Platform](#platform-1)\n"
    )


def test_update_changelog_toc_replaces_marker_block_only() -> None:
    from scripts.registry.generate_docs import (
        CHANGELOG_TOC_END,
        CHANGELOG_TOC_START,
        update_changelog_toc,
    )

    changelog = (
        f"# Changelog\n\nintro\n\n{CHANGELOG_TOC_START}\nstale\n{CHANGELOG_TOC_END}\n\n"
        "## squad-map\n\n### v1 (2026-01-01)\n\n- did a thing\n"
    )
    updated = update_changelog_toc(changelog)

    assert "stale" not in updated
    assert "- [squad-map](#squad-map)" in updated
    assert "intro" in updated
    assert "## squad-map" in updated  # content outside the marker block is untouched


def test_update_changelog_toc_raises_when_markers_missing() -> None:
    from scripts.registry.generate_docs import update_changelog_toc

    with pytest.raises(ValueError, match="missing marker block"):
        update_changelog_toc("# Changelog\n\n## squad-map\n\n### v1 (2026-01-01)\n\n- x\n")


def test_issue_template_skill_dropdown_is_regenerated_from_the_registry() -> None:
    from scripts.registry.generate_issue_templates import render_issue_template

    form = (
        "name: Bug report\n"
        "body:\n"
        "  - type: dropdown\n"
        "    id: skill\n"
        "    attributes:\n"
        "      label: Affected skill\n"
        "      options:\n"
        "        - pr-review\n"
        "        - retired-skill\n"
        "        - Other / not sure\n"
        "    validations:\n"
        "      required: true\n"
    )

    rendered = render_issue_template(form, ["squad-map", "pr-review"])

    options = [line.strip() for line in rendered.splitlines() if line.startswith("        - ")]
    # Registered ids in sorted order; every option that is not a registered id (the form's own
    # extra choices, and a skill that has since left the registry) keeps its place after them.
    assert options == ["- pr-review", "- squad-map", "- retired-skill", "- Other / not sure"]
    assert "# GENERATED from skills.yaml" in rendered
    assert "    validations:\n      required: true\n" in rendered

    # Idempotent: a second pass over generated output reproduces it exactly.
    assert render_issue_template(rendered, ["squad-map", "pr-review"]) == rendered


def test_issue_template_without_a_skill_dropdown_is_not_generated() -> None:
    from scripts.registry.generate_issue_templates import render_issue_template

    form = "name: New skill proposal\nbody:\n  - type: input\n    id: name\n"

    assert render_issue_template(form, ["squad-map"]) is None


def _registry_with_escalations(targets: dict[str, list[str]]):
    from scripts.registry.models import (
        CompositionSpec,
        InstallSpec,
        LintSpec,
        Registry,
        SkillEntry,
    )

    return Registry(
        schema_version=1,
        skills={
            skill_id: SkillEntry(
                path=skill_id,
                category="review",
                invocation="ambient",
                hosts={},
                install=InstallSpec(),
                lint=LintSpec(skill_md_max_lines=180, target=skill_id),
                composition=CompositionSpec(escalation_targets=list(escalations)),
            )
            for skill_id, escalations in targets.items()
        },
    )


_ESCALATION_DOC = (
    "# Cross-skill escalation (shared)\n\n"
    "## 1. Symmetric matrix (forward escalations)\n\n"
    "| Trigger | From → To | Handoff artifact | User prompt template |\n"
    "|---|---|---|---|\n"
    "{rows}"
    "\n## 2. Reverse escalations\n"
)


def test_repository_doc_layout_tree_reports_a_skill_missing_from_the_tree(tmp_path: Path) -> None:
    # docs/REPOSITORY.md's hand-typed Layout tree and its generated registry-skills-table
    # are two statements of "what skills exist" -- a skill added to the registry without
    # updating the tree leaves the file contradicting itself (this happened for real in
    # commit 9d6b726, which added codebase-architecture-review/module-design to the
    # generated table but not the tree above it).
    from scripts.registry.repository_doc_sync import validate_repository_doc_layout_tree

    doc = tmp_path / "docs" / "REPOSITORY.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "# Repository guide\n\n## Layout\n\n```\nsoftware-builder/\n"
        "├── README.md              # Top-level install + usage\n"
        "├── pr-review/             # PR review skill\n"
        "└── squad-map/             # Ownership mapping skill\n"
        "```\n",
        encoding="utf-8",
    )
    registry = _registry_with_escalations({"pr-review": [], "squad-map": [], "incident-rca": []})

    errors = validate_repository_doc_layout_tree(tmp_path, registry)

    assert any("missing registered skill(s)" in e and "incident-rca" in e for e in errors)


def test_repository_doc_layout_tree_passes_when_every_skill_is_listed(tmp_path: Path) -> None:
    from scripts.registry.repository_doc_sync import validate_repository_doc_layout_tree

    doc = tmp_path / "docs" / "REPOSITORY.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "# Repository guide\n\n## Layout\n\n```\nsoftware-builder/\n"
        "├── pr-review/             # PR review skill\n"
        "└── squad-map/             # Ownership mapping skill\n"
        "```\n",
        encoding="utf-8",
    )
    registry = _registry_with_escalations({"pr-review": [], "squad-map": []})

    assert validate_repository_doc_layout_tree(tmp_path, registry) == []


def test_escalation_sync_reports_registry_edges_the_doc_never_documents(tmp_path: Path) -> None:
    from scripts.registry.escalation_sync import validate_escalation_matrix

    doc = tmp_path / "docs" / "skill-framework" / "shared" / "cross-skill-escalation.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        _ESCALATION_DOC.format(rows="| t | pr-review → squad-map | a | p |\n"),
        encoding="utf-8",
    )
    registry = _registry_with_escalations({"pr-review": ["squad-map", "incident-rca"], "squad-map": [], "incident-rca": []})

    errors = validate_escalation_matrix(tmp_path, registry)

    assert any("missing registry escalation edges: pr-review → incident-rca" in e for e in errors)


def test_escalation_sync_resolves_shorthand_and_multi_target_rows(tmp_path: Path) -> None:
    """`k8s` is the matrix's long-standing shorthand, and one From → To cell can name several
    destinations -- both must resolve to registered ids rather than read as dangling."""
    from scripts.registry.escalation_sync import validate_escalation_matrix

    doc = tmp_path / "docs" / "skill-framework" / "shared" / "cross-skill-escalation.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        _ESCALATION_DOC.format(rows="| t | pr-review → k8s + incident-rca | a | p |\n"),
        encoding="utf-8",
    )
    registry = _registry_with_escalations(
        {
            "pr-review": ["k8s-overprovisioning-datadog", "incident-rca"],
            "k8s-overprovisioning-datadog": [],
            "incident-rca": [],
        }
    )

    assert validate_escalation_matrix(tmp_path, registry) == []


def test_escalation_sync_rejects_an_endpoint_that_is_not_a_registered_skill(tmp_path: Path) -> None:
    from scripts.registry.escalation_sync import validate_escalation_matrix

    doc = tmp_path / "docs" / "skill-framework" / "shared" / "cross-skill-escalation.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        _ESCALATION_DOC.format(rows="| t | pr-review → renamed-skill | a | p |\n"),
        encoding="utf-8",
    )
    registry = _registry_with_escalations({"pr-review": []})

    errors = validate_escalation_matrix(tmp_path, registry)

    assert any("routes to unregistered skills" in e and "renamed-skill" in e for e in errors)


def _routing_doc(rows: str) -> str:
    return (
        "# Skill Routing (shared)\n\n"
        "## Routing table\n\n"
        "| User intent / keywords | Route to | NOT these |\n"
        "|---|---|---|\n" + rows + "\n## Next section\n"
    )


def test_skill_md_not_these_must_be_a_subset_of_the_shared_routing_row(tmp_path: Path) -> None:
    from scripts.registry.routing_sync import validate_skill_not_these_subsets

    doc = tmp_path / "docs" / "skill-framework" / "shared" / "skill-routing.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(_routing_doc("| kw | **pr-review** | incident-rca |\n"), encoding="utf-8")
    (tmp_path / "pr-review").mkdir()
    (tmp_path / "pr-review" / "SKILL.md").write_text(
        "# pr-review\n\n## When NOT to use\n\n"
        "| Request | Use instead |\n|---|---|\n"
        "| Outage window | **incident-rca** |\n"
        "| Webhook-triggered run | **pr-gatekeeper** |\n",
        encoding="utf-8",
    )
    registry = _registry_with_escalations({"pr-review": []})

    errors = validate_skill_not_these_subsets(tmp_path, registry)

    assert len(errors) == 1
    assert "pr-review: SKILL.md routes away to pr-gatekeeper" in errors[0]


def test_skill_not_these_subset_unions_every_row_the_skill_owns(tmp_path: Path) -> None:
    """A skill can own several routing rows (one per mode); the exclusions of all of them
    together are what its own table may draw from."""
    from scripts.registry.routing_sync import validate_skill_not_these_subsets

    doc = tmp_path / "docs" / "skill-framework" / "shared" / "skill-routing.md"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        _routing_doc(
            "| kw | **prd-architect** | pr-review |\n"
            "| kw | **prd-architect** Review Mode | test-writer (generate tests) |\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "prd-architect").mkdir()
    (tmp_path / "prd-architect" / "SKILL.md").write_text(
        "# prd-architect\n\n## When to use / NOT to use\n\n"
        "| Use | Not |\n|---|---|\n"
        "| Define MVP | **test-writer** — generate tests |\n"
        "| Review a diff | **pr-review** |\n",
        encoding="utf-8",
    )
    registry = _registry_with_escalations({"prd-architect": []})

    assert validate_skill_not_these_subsets(tmp_path, registry) == []
