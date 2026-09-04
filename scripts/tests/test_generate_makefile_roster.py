"""Tests for the generated Makefile skill roster and per-skill install rules."""

from __future__ import annotations

from pathlib import Path

from scripts.registry.generate_makefile_roster import (
    ALL_SKILLS_ORDER,
    EXTRA_INSTALL_PREREQUISITES,
    INSTALL_TARGET_ALIASES,
    generate_makefile_roster,
    install_target,
    render_makefile_roster,
)
from scripts.registry.load import load_registry

ROOT = Path(__file__).resolve().parents[2]


def test_render_matches_frozen_order_on_real_repo() -> None:
    registry = load_registry(ROOT)
    rendered = render_makefile_roster(registry)
    assert f"ALL_SKILLS := {' '.join(ALL_SKILLS_ORDER)}\n" in rendered
    assert set(registry.skills) == set(ALL_SKILLS_ORDER)


def test_unknown_skill_appends_after_frozen_order_instead_of_raising(tmp_path: Path) -> None:
    from scripts.registry.schema import parse_registry

    registry_file = tmp_path / "skills.yaml"
    registry_file.write_text(
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
    registry = parse_registry(registry_file)

    rendered = render_makefile_roster(registry)

    assert "ALL_SKILLS := solo\n" in rendered
    assert "install-solo:\n\tbash scripts/install.sh solo\n" in rendered
    assert "install-claude-solo:\n\tbash scripts/install.sh --agent claude-user solo\n" in rendered


def test_generate_makefile_roster_writes_expected_path(tmp_path: Path) -> None:
    registry = load_registry(ROOT)
    outputs = generate_makefile_roster(tmp_path, registry)
    assert set(outputs) == {tmp_path / "make" / "generated-roster.mk"}


def test_every_registered_skill_gets_both_install_rules() -> None:
    registry = load_registry(ROOT)
    rendered = render_makefile_roster(registry)
    for skill_id in registry.skills:
        assert f"\n{install_target(skill_id)}:" in rendered, skill_id
        assert f"\n{install_target(skill_id, host_prefix='claude-')}:" in rendered, skill_id


def test_install_rule_prerequisites_are_the_registry_requires() -> None:
    """The Make graph's install edges ARE install.requires -- not a copy of them."""
    registry = load_registry(ROOT)
    rendered = render_makefile_roster(registry)
    for skill_id, entry in registry.skills.items():
        for prefix in ("", "claude-"):
            expected = [install_target(dep, host_prefix=prefix) for dep in entry.install.requires]
            expected.extend(EXTRA_INSTALL_PREREQUISITES.get(skill_id, ()))
            target = install_target(skill_id, host_prefix=prefix)
            rule = next(
                line for line in rendered.splitlines() if line.startswith(f"{target}:")
            )
            assert rule.split(":", 1)[1].split() == expected, target


def test_host_independent_prerequisites_are_not_claude_prefixed() -> None:
    registry = load_registry(ROOT)
    rendered = render_makefile_roster(registry)
    assert "install-claude-incident-rca: install-incident-rca-deps\n" in rendered
    assert "install-claude-install-incident-rca-deps" not in rendered


def test_alias_targets_keep_their_historical_names() -> None:
    assert INSTALL_TARGET_ALIASES["k8s-overprovisioning-datadog"] == "k8s-overprovisioning"
    registry = load_registry(ROOT)
    rendered = render_makefile_roster(registry)
    assert "install-k8s-overprovisioning:\n\tbash scripts/install.sh k8s-overprovisioning-datadog\n" in rendered
    assert "install-k8s-overprovisioning-datadog:" not in rendered


def test_generated_install_targets_are_declared_phony() -> None:
    registry = load_registry(ROOT)
    rendered = render_makefile_roster(registry)
    phony = next(line for line in rendered.splitlines() if line.startswith(".PHONY:"))
    declared = set(phony.removeprefix(".PHONY:").split())
    for skill_id in registry.skills:
        assert install_target(skill_id) in declared, skill_id
        assert install_target(skill_id, host_prefix="claude-") in declared, skill_id
