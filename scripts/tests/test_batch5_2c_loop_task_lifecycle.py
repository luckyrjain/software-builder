from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "loop-task-implementer"


def test_loop_task_declares_shared_lifecycle_contract():
    contract = SKILL / "reference/review-lifecycle-contract.yaml"
    assert contract.exists()
    data = yaml.safe_load(contract.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["shared_contracts"]["change_identity"].endswith("change-identity.yaml")
    assert data["shared_contracts"]["review_evidence"].endswith("review-evidence.yaml")
    assert data["completion_requires"] == [
        "current_change_identity_valid",
        "lens_a_evidence_fresh",
        "lens_b_evidence_fresh",
        "both_lenses_clean_for_same_change_identity",
        "authoritative_ci_green_for_current_head",
        "no_unresolved_third_party_branch_change",
    ]


def test_state_schema_carries_shared_identity_requirements_and_lens_evidence():
    data = yaml.safe_load((SKILL / "reference/state-schema.yaml").read_text(encoding="utf-8"))
    assert "requirements_ref" in data["task"]
    assert "change_identity" in data["workspace"]
    assert "conflict_resolution_occurred" in data["workspace"]
    assert "conflict_resolution_provenance" in data["workspace"]
    for lens in ("lens_a", "lens_b"):
        assert "review_evidence" in data["review"][lens]
        assert "reviewed_change_identity" in data["review"][lens]


def test_reviewer_evidence_adapter_emits_shared_review_evidence():
    text = (SKILL / "workflow/reviewer-evidence.md").read_text(encoding="utf-8")
    assert "review_evidence" in text
    assert "change_identity" in text
    assert "docs/skill-framework/shared/review-evidence.yaml" in text
    assert "defect" in text and "suggestion" in text and "question" in text


def test_orchestrator_path_loads_mandatory_lifecycle_overlay():
    lazy = (SKILL / "reference/lazy-load-index.md").read_text(encoding="utf-8")
    phase = (SKILL / "reference/phase-index.md").read_text(encoding="utf-8")
    overlay = (SKILL / "workflow/orchestrator-lifecycle.md").read_text(encoding="utf-8")
    assert "mandatory [workflow/orchestrator-lifecycle.md]" in lazy
    assert "orchestrator-lifecycle.md" in phase
    for token in (
        "validate_loop_lifecycle.py",
        "current `change_identity`",
        "conflict_resolution_occurred",
        "third_party_change_detected",
        "required checks",
        "current head",
        "zero validation errors",
    ):
        assert token in overlay


def test_lifecycle_gate_revalidates_before_ready_or_merge():
    text = (SKILL / "workflow/lifecycle-gate.md").read_text(encoding="utf-8")
    required = (
        "validate_loop_lifecycle.py",
        "current `change_identity`",
        "conflict_resolution_occurred",
        "third_party_change_detected",
        "required checks",
        "current head",
    )
    for token in required:
        assert token in text


def test_lifecycle_validator_is_packaged_and_fail_closed():
    script = SKILL / "scripts/validate_loop_lifecycle.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    assert "review_contract_runtime.py" in text
    assert "validate_review_evidence" in text
    assert "third_party_change_detected" in text
    assert "conflict_resolution_occurred" in text
    assert "required checks must be green before lifecycle readiness" in text
    assert "accepted_blocking_findings_open must be integer 0" in text
