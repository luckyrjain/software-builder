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
    for requirement in (
        "current_change_identity_valid",
        "lens_a_evidence_fresh",
        "lens_b_evidence_fresh",
        "both_lenses_clean_for_same_change_identity",
        "review_isolation_gate_satisfied",
        "no_security_sensitive_needs_evidence_unresolved",
        "authoritative_ci_green_for_current_head",
        "no_unresolved_third_party_branch_change",
    ):
        assert requirement in data["completion_requires"]


def test_state_schema_carries_shared_identity_requirements_and_lens_evidence():
    data = yaml.safe_load((SKILL / "reference/state-schema.yaml").read_text(encoding="utf-8"))
    assert "requirements_ref" in data["task"]
    assert "change_identity" in data["workspace"]
    assert "conflict_resolution_occurred" in data["workspace"]
    assert "conflict_resolution_provenance" in data["workspace"]
    for lens in ("lens_a", "lens_b"):
        lens_state = data["review"][lens]
        assert "review_evidence" in lens_state
        assert "reviewed_change_identity" in lens_state
        assert "isolation_status" in lens_state
        assert "isolation_exception_authorized" in lens_state
        assert "isolation_exception_provenance" in lens_state
    assert "security_sensitive_needs_evidence_unresolved" in data["merge_readiness"]


def test_reviewer_evidence_adapter_emits_shared_review_evidence_after_adjudication():
    text = (SKILL / "workflow/reviewer-evidence.md").read_text(encoding="utf-8")
    for token in (
        "adjudication_verdicts",
        "after the Orchestrator adjudicates",
        "accepted blocking findings that remain open",
        "REJECTED",
        "review_evidence",
        "change_identity",
        "docs/skill-framework/shared/review-evidence.yaml",
        "inspection_status",
        "findings.defect` is empty",
        "NOT_ISOLATED",
    ):
        assert token in text


def test_phase_order_adjudicates_before_portable_evidence():
    phase = (SKILL / "reference/phase-index.md").read_text(encoding="utf-8")
    assert phase.index("adjudicate Lens A proposed findings") < phase.index(
        "normalize/validate Lens A review_evidence"
    )
    assert phase.index("adjudicate Lens B proposed findings") < phase.index(
        "normalize/validate Lens B review_evidence"
    )


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
        "security_sensitive_needs_evidence_unresolved",
        "isolation_exception_provenance",
        "required checks",
        "current head",
        "zero validation errors",
    ):
        assert token in overlay


def test_lifecycle_gate_revalidates_before_ready_or_merge():
    text = (SKILL / "workflow/lifecycle-gate.md").read_text(encoding="utf-8")
    for token in (
        "validate_loop_lifecycle.py",
        "current `change_identity`",
        "conflict_resolution_occurred",
        "third_party_change_detected",
        "security_sensitive_needs_evidence_unresolved",
        "NOT_ISOLATED",
        "isolation exception",
        "required checks",
        "current head",
        "explicit `null`",
    ):
        assert token in text


def test_lifecycle_validator_is_packaged_and_fail_closed():
    script = SKILL / "scripts/validate_loop_lifecycle.py"
    assert script.exists()
    text = script.read_text(encoding="utf-8")
    for token in (
        "review_contract_runtime.py",
        "validate_review_evidence",
        "third_party_change_detected",
        "conflict_resolution_occurred",
        "required checks must be green before lifecycle readiness",
        "accepted_blocking_findings_open must be integer 0",
        "security_sensitive_needs_evidence_unresolved must be integer 0",
        "NOT_ISOLATED blocks lifecycle readiness",
    ):
        assert token in text
