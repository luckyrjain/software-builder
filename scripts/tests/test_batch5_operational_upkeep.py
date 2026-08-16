from __future__ import annotations

from pathlib import Path

from scripts.operational_upkeep import (
    _validate_deprecation_mapping,
    build_health_report,
    classify_diff,
    classify_file_role,
    codeowners_for,
    load_policy,
    render_health_markdown,
    validate_diff_risk,
    validate_policy,
)
from scripts.registry.install_targets_sync import _read_makefile_graph


ROOT = Path(__file__).resolve().parents[2]


def _phony_targets(makefile: Path) -> set[str]:
    targets: set[str] = set()
    for line in makefile.read_text(encoding="utf-8").splitlines():
        if line.startswith(".PHONY:"):
            targets.update(line.removeprefix(".PHONY:").split())
    return targets


def test_lint_prd_architect_is_declared_phony() -> None:
    assert "lint-prd-architect" in _phony_targets(ROOT / "Makefile")


def test_install_target_scan_follows_literal_make_includes(tmp_path: Path) -> None:
    (tmp_path / "make").mkdir()
    (tmp_path / "Makefile").write_text("include make/core.mk\n", encoding="utf-8")
    (tmp_path / "make" / "core.mk").write_text(
        "install-example:\n\tbash scripts/install.sh example\n",
        encoding="utf-8",
    )
    text = _read_makefile_graph(tmp_path)
    assert "bash scripts/install.sh example" in text


def test_install_target_scan_ignores_dynamic_and_escaping_includes(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text(
        "include $(DYNAMIC)\ninclude ../outside.mk\n",
        encoding="utf-8",
    )
    (tmp_path.parent / "outside.mk").write_text("should-not-load\n", encoding="utf-8")
    assert "should-not-load" not in _read_makefile_graph(tmp_path)


def test_operational_policy_validates_repository() -> None:
    assert validate_policy(ROOT) == []


def test_file_roles_separate_runtime_reference_and_maintainer_surfaces() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    assert classify_file_role("pr-review/SKILL.md", policy) == "runtime"
    assert classify_file_role("pr-review/workflow/inputs.md", policy) == "runtime"
    assert classify_file_role("pr-review/reference/smoke-test.md", policy) == "reference"
    assert classify_file_role("scripts/registry/eval_contracts.yaml", policy) == "maintainer"
    assert classify_file_role("make/core.mk", policy) == "maintainer"


def test_contract_owner_resolution_uses_matching_codeowners_rule() -> None:
    codeowners = (ROOT / "CODEOWNERS").read_text(encoding="utf-8")
    assert "@luckyrjain" in codeowners_for("scripts/registry/eval_contracts.yaml", codeowners)
    assert "@luckyrjain" in codeowners_for("docs/skill-framework/shared/safe-output.md", codeowners)
    assert "@luckyrjain" in codeowners_for("make/core.mk", codeowners)


def test_deprecated_contract_fails_closed_when_lifecycle_metadata_is_missing() -> None:
    required = {"deprecated_since", "replacement", "remove_after", "migration_note", "aliases"}
    errors = _validate_deprecation_mapping(
        {"status": "deprecated", "deprecation": {"replacement": "route.new"}},
        "fixture.yaml",
        required,
    )
    assert len(errors) == 1
    assert "deprecated_since" in errors[0]
    assert "remove_after" in errors[0]
    assert "migration_note" in errors[0]
    assert "aliases" in errors[0]


def test_health_report_is_deterministic_with_complete_provenance() -> None:
    first = build_health_report(ROOT, revision="deadbeef")
    second = build_health_report(ROOT, revision="deadbeef")
    assert first == second
    provenance = first["provenance"]
    assert provenance["repository_revision"] == "deadbeef"
    assert provenance["registry_schema_version"] == 1
    assert provenance["prompt_bundle_version"] == "1"
    assert provenance["evaluator_version"] == "1"
    assert provenance["operational_policy_version"] == "1.1"

    health = first["health"]
    assert health["skills"] >= 23
    assert health["stable_routes"] >= 6
    assert health["route_token_budget_coverage"] == health["stable_routes"]
    assert health["stable_stop_conditions"] >= 5
    assert health["stable_report_fields"] >= 6
    assert health["contract_owners"] >= 7
    assert health["external_dependency_count"] > 0
    assert health["orphan_runtime_modules"] == []

    markdown = render_health_markdown(first)
    assert "Repository revision: `deadbeef`" in markdown
    assert "Prompt bundle: `1`" in markdown
    assert "Evaluator: `1`" in markdown
    assert "Route token-budget coverage:" in markdown
    assert "Orphan runtime modules: **0**" in markdown


def test_prompt_diff_risk_uses_highest_matching_class() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    risk, matched = classify_diff(
        [
            "README.md",
            "pr-review/workflow/phase-5.md",
            "scripts/registry/capability_catalog.yaml",
            "docs/skill-framework/shared/skill-routing.md",
        ],
        policy,
    )
    assert risk == "routing"
    assert matched == ["editorial", "behavioral", "authority-capability", "routing"]


def test_high_risk_prompt_diff_requires_test_or_eval_evidence() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    risk, errors = validate_diff_risk(
        ["docs/skill-framework/shared/skill-routing.md"],
        policy,
    )
    assert risk == "routing"
    assert errors and "requires changed eval/test evidence" in errors[0]

    risk, errors = validate_diff_risk(
        [
            "docs/skill-framework/shared/skill-routing.md",
            "scripts/tests/test_batch5_operational_upkeep.py",
        ],
        policy,
    )
    assert risk == "routing"
    assert errors == []
