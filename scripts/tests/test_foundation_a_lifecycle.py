from pathlib import Path

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def _owner(prompt: str) -> str | None:
    result = dispatch_prompt(ROOT, load_registry(ROOT), prompt)
    assert result.status == "selected", result
    return result.owner


def test_ready_prd_routes_to_system_design_before_architecture_review() -> None:
    assert _owner("Turn this ready PRD into the implementation design") == "system-design"


def test_numbered_pr_readiness_is_owned_by_production_readiness_review() -> None:
    # Foundation A shipped before production-readiness-review existed, so this prompt was
    # deliberately unowned (no_match) as a placeholder guard against another skill silently
    # claiming it first. PR D added production-readiness-review as the explicit owner.
    assert _owner("Is PR #123 production ready?") == "production-readiness-review"


def test_architecture_rework_is_recommendation_not_runtime_cycle() -> None:
    registry = load_registry(ROOT)
    assert "system-design" not in registry.skills["architecture-review"].composition.invokes


def test_foundation_a_lifecycle_consume_fields_are_exact() -> None:
    load_registry(ROOT)
    contracts = load_unique_yaml_file(ROOT / "skills.yaml")["contracts"]["composition"]["skills"]
    sd = contracts["system-design"]
    ar = contracts["architecture-review"]
    assert sd["consume_fields"]["prd_report"] == [
        "title", "build_readiness", "depth", "response_mode",
        "assessment_target", "normalized_decision", "evidence_refs",
    ]
    assert sd["consume_fields"]["architecture_review_report"] == [
        "title", "decision", "assessment_target", "normalized_decision", "evidence_refs",
    ]
    assert ar["consume_fields"]["system_design_spec"] == [
        "title", "readiness", "assessment_target", "normalized_decision", "evidence_refs",
    ]
    assert ar["consume_fields"]["prd_report"] == [
        "title", "build_readiness", "depth", "response_mode",
        "assessment_target", "normalized_decision", "evidence_refs",
    ]
