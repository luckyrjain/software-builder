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


def test_gate_blocks_mandatory_unavailable_even_when_partial():
    gate = _text("pr-review/workflow/phase-2-3-gate.md")
    assert "any** `review_evidence.unable_to_inspect[]` entry with `mandatory: true`" in gate.lower()
    assert "partial` may reach phase 3 **only when every unavailable entry is non-mandatory" in gate.lower()
    assert "mandatory unavailable coverage never" in gate.lower()


def test_phase5_consumes_and_renders_inspection_coverage():
    phase5 = _text("pr-review/workflow/phase-5.md")
    assert "review_evidence: object" in phase5
    assert "inspection_plan: object" in phase5
    assert "## Coverage gaps (Batch 5.2B)" in phase5
    assert "Mandatory inspection unavailable" in phase5
    assert "inspection_status: partial" in phase5
    assert "inspection_status: unable" in phase5
    assert "Recommendation capped — never ✅ Approve" in phase5


def test_phase5_renders_coverage_gaps_before_suppressed_items():
    phase5 = _text("pr-review/workflow/phase-5.md")
    output_order = phase5.split("## Output order (end of review)", 1)[1]
    assert output_order.index("**Coverage gaps**") < output_order.index("**Not raised (suppressed)**")
