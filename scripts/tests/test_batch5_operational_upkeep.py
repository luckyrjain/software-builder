from __future__ import annotations

from pathlib import Path

from scripts.operational_upkeep import (
    build_health_report,
    classify_diff,
    classify_file_role,
    load_policy,
    render_health_markdown,
    validate_diff_risk,
    validate_policy,
)


ROOT = Path(__file__).resolve().parents[2]


def _phony_targets(makefile: Path) -> set[str]:
    targets: set[str] = set()
    for line in makefile.read_text(encoding="utf-8").splitlines():
        if line.startswith(".PHONY:"):
            targets.update(line.removeprefix(".PHONY:").split())
    return targets


def test_lint_prd_architect_is_declared_phony() -> None:
    assert "lint-prd-architect" in _phony_targets(ROOT / "Makefile")


def test_operational_policy_validates_repository() -> None:
    assert validate_policy(ROOT) == []


def test_file_roles_separate_runtime_reference_and_maintainer_surfaces() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    assert classify_file_role("pr-review/SKILL.md", policy) == "runtime"
    assert classify_file_role("pr-review/workflow/inputs.md", policy) == "runtime"
    assert classify_file_role("pr-review/reference/smoke-test.md", policy) == "reference"
    assert classify_file_role("scripts/registry/eval_contracts.yaml", policy) == "maintainer"


def test_health_report_is_deterministic_with_explicit_revision() -> None:
    first = build_health_report(ROOT, revision="deadbeef")
    second = build_health_report(ROOT, revision="deadbeef")
    assert first == second
    assert first["provenance"]["repository_revision"] == "deadbeef"
    assert first["provenance"]["operational_policy_version"] == "1.0"
    assert first["health"]["skills"] >= 23
    assert first["health"]["stable_routes"] >= 6
    assert first["health"]["stable_stop_conditions"] >= 5
    assert first["health"]["stable_report_fields"] >= 6
    markdown = render_health_markdown(first)
    assert "Repository revision: `deadbeef`" in markdown
    assert "Stable IDs:" in markdown


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
