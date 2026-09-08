from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "loop-task-implementer"


def test_loop_task_declares_shared_lifecycle_contract():
    contract = SKILL / "reference/review-lifecycle-contract.yaml"
    assert contract.exists()
    data = yaml.safe_load(contract.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["shared_contract_path_base"] == "package_or_repository_root"
    assert data["shared_contracts"]["change_identity"] == "docs/skill-framework/shared/change-identity.yaml"
    assert data["shared_contracts"]["review_evidence"] == "docs/skill-framework/shared/review-evidence.yaml"
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
    for binding in (
        "third_party_change_checked_head",
        "lens_a_review_generation",
        "lens_b_review_generation",
        "lens_a_review_evidence_generation",
        "lens_b_review_evidence_generation",
        "lens_a_isolation_exception_change_identity",
        "lens_b_isolation_exception_change_identity",
        "lens_a_isolation_exception_review_generation",
        "lens_b_isolation_exception_review_generation",
    ):
        assert binding in data["state_binding"]


def test_state_schema_carries_shared_identity_requirements_and_lens_evidence():
    data = yaml.safe_load((SKILL / "reference/state-schema.yaml").read_text(encoding="utf-8"))
    assert data["workflow_version"] == "1.7"
    assert "requirements_ref" in data["task"]
    assert "change_identity" in data["workspace"]
    assert "conflict_resolution_occurred" in data["workspace"]
    assert "conflict_resolution_provenance" in data["workspace"]
    assert "third_party_change_checked_head" in data["workspace"]
    assert data["workspace"]["third_party_change_detected"] is None
    for lens in ("lens_a", "lens_b"):
        lens_state = data["review"][lens]
        assert lens_state["review_generation"] == 0
        assert lens_state["review_evidence_generation"] is None
        assert "review_evidence" in lens_state
        assert "reviewed_change_identity" in lens_state
        assert "isolation_status" in lens_state
        assert "isolation_exception_authorized" in lens_state
        assert "isolation_exception_provenance" in lens_state
        assert "isolation_exception_change_identity" in lens_state
        assert "isolation_exception_review_generation" in lens_state
    assert "security_sensitive_needs_evidence_unresolved" in data["merge_readiness"]


def test_lifecycle_workflow_versions_track_behavior_changes():
    for name in ("orchestrator-lifecycle.md", "reviewer-evidence.md", "lifecycle-gate.md"):
        text = (SKILL / "workflow" / name).read_text(encoding="utf-8")
        assert "workflow_version: 1.7" in text


def test_reviewer_evidence_adapter_consumes_generation_and_persists_evidence_generation():
    text = (SKILL / "workflow/reviewer-evidence.md").read_text(encoding="utf-8")
    for token in (
        "after the Orchestrator adjudicates",
        "does **not** increment the review generation",
        "review_evidence_generation",
        "review_evidence_generation == review_generation",
        "Never advance `review_evidence_generation` before new evidence",
        "accepted blocking findings that remain open",
        "../../docs/skill-framework/shared/review-evidence.yaml",
        "isolation_exception_review_generation",
    ):
        assert token in text


def test_phase_order_increments_generation_before_adjudication_and_remediates_a_before_b():
    phase = (SKILL / "reference/phase-index.md").read_text(encoding="utf-8")
    assert phase.index("increment Lens A review_generation") < phase.index("adjudicate Lens A proposed findings")
    assert phase.index("adjudicate Lens A proposed findings") < phase.index("normalize/validate Lens A review_evidence")
    assert phase.index("normalize/validate Lens A review_evidence") < phase.index("if Lens A has accepted findings: dispatch Builder remediation")
    assert phase.index("if Lens A has accepted findings: dispatch Builder remediation") < phase.index("dispatch Reviewer Lens B")
    assert phase.index("increment Lens B review_generation") < phase.index("adjudicate Lens B proposed findings")
    assert phase.index("adjudicate Lens B proposed findings") < phase.index("normalize/validate Lens B review_evidence")
    assert "each returned rerun increments that lens generation" in phase


def test_report_template_keeps_human_provenance_out_of_inline_code():
    report = (SKILL / "report-template.md").read_text(encoding="utf-8")
    assert "provenance: <escaped/redacted provenance>" in report
    assert "`<provenance>`" not in report
    assert "identity head `<isolation_exception_change_identity.head_sha>`" in report
    assert "identity `<isolation_exception_change_identity>`" not in report


def test_escalation_machine_state_requires_dynamic_outer_fence():
    report = (SKILL / "report-template.md").read_text(encoding="utf-8")
    assert "max(3, longest_run + 1)" in report
    assert "Do **not** use a fixed triple-backtick fence for this block" in report
    assert "<DYNAMIC_FENCE>yaml" in report
    assert "requirements_ref:" in report
    assert "change_identity:" in report


def test_orchestrator_path_loads_mandatory_lifecycle_overlay():
    lazy = (SKILL / "reference/lazy-load-index.md").read_text(encoding="utf-8")
    phase = (SKILL / "reference/phase-index.md").read_text(encoding="utf-8")
    overlay = (SKILL / "workflow/orchestrator-lifecycle.md").read_text(encoding="utf-8")
    assert "mandatory [workflow/orchestrator-lifecycle.md]" in lazy
    assert "orchestrator-lifecycle.md" in phase
    for token in (
        "python3",
        "<skill_root>/scripts/validate_loop_lifecycle.py",
        "third_party_change_checked_head",
        "review_generation",
        "review_evidence_generation",
        "isolation_exception_review_generation",
        "current head",
        "exit code `0`",
    ):
        assert token in overlay


def test_lifecycle_gate_revalidates_before_ready_or_merge():
    text = (SKILL / "workflow/lifecycle-gate.md").read_text(encoding="utf-8")
    for token in (
        "python3",
        "<skill_root>/scripts/validate_loop_lifecycle.py",
        "third_party_change_checked_head",
        "review_generation",
        "review_evidence_generation",
        "review_evidence_generation == review_generation",
        "isolation_exception_review_generation",
        "current head",
        "exit code `0`",
    ):
        assert token in text


def test_lifecycle_validator_is_packaged_and_fail_closed():
    text = (SKILL / "scripts/validate_loop_lifecycle.py").read_text(encoding="utf-8")
    for token in (
        "review_contract_runtime.py",
        "validate_review_evidence",
        "third_party_change_checked_head",
        "review_generation",
        "review_evidence_generation",
        "isolation_exception_review_generation",
        "required checks must be green before lifecycle readiness",
        "accepted_blocking_findings_open must be integer 0",
        "security_sensitive_needs_evidence_unresolved must be integer 0",
        "NOT_ISOLATED blocks lifecycle readiness",
        "def main(",
        "--state",
    ):
        assert token in text
