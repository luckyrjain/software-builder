from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str):
    return yaml.safe_load(_text(path))


def test_skill_requires_coverage_review_before_evidence():
    skill = _text("pr-review/SKILL.md")
    coverage = skill.index("workflow/phase-2-coverage-review.md")
    evidence = skill.index("workflow/phase-2-evidence.md")
    assert coverage < evidence
    assert "same finding pipeline" in skill.lower()
    assert "regenerate combined grouping/metrics" in skill.lower()


def test_workflow_route_places_coverage_review_between_phase2_and_evidence():
    workflow = _yaml("pr-review/workflow-contract.yaml")
    for route in ("posting", "chat_only"):
        phases = workflow["routes"][route]["phases"]
        assert phases.index("2") < phases.index("2-coverage-review") < phases.index("2-evidence")


def test_phase_references_match_execution_section_names():
    planning = _text("pr-review/workflow/phase-1-2-coverage.md")
    coverage = _text("pr-review/workflow/phase-2-coverage-review.md")
    evidence = _text("pr-review/workflow/phase-2-evidence.md")
    execution = _text("pr-review/reference/review-coverage-execution.md")

    assert "§Phase 1→2 coverage" in planning
    assert "## Phase 1→2 coverage" in execution
    assert "§Coverage review" in coverage
    assert "## Coverage review" in execution
    assert "§Phase 2 evidence" in evidence
    assert "## Phase 2 evidence" in execution


def test_portable_id_and_evidence_policy_is_explicit():
    contract = _yaml("pr-review/reference/review-coverage-contract.yaml")
    classification = contract["finding_classification"]
    ids = classification["portable_id_policy"]
    evidence = classification["portable_evidence_policy"]

    assert ids["defect"] == "preserve_existing_PRR_id"
    assert ids["suggestion"].startswith("PRS_dash_first12_sha256")
    assert ids["question"].startswith("PRQ_dash_first12_sha256")
    assert evidence["empty_evidence_forbidden"] is True
