from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _yaml(path: str):
    return yaml.safe_load(_text(path))


def test_pr_review_has_machine_inspection_contract_for_batch5_2b_surfaces():
    contract = _yaml("pr-review/reference/review-coverage-contract.yaml")
    assert contract["schema_version"] == 1
    assert contract["consumer"] == "pr-review"
    assert contract["shared_contracts"]["change_identity"].endswith("change-identity.yaml")
    assert contract["shared_contracts"]["review_evidence"].endswith("review-evidence.yaml")

    surfaces = contract["inspection_surfaces"]
    for surface in (
        "cross_file_impact",
        "hidden_consumers",
        "schema_migration_compatibility",
        "rollout_rollback",
        "test_quality",
        "dependency_config_iac",
    ):
        assert surface in surfaces
        assert "trigger" in surfaces[surface]
        assert "evidence" in surfaces[surface]

    assert contract["unable_to_inspect"]["machine_field"] == "review_evidence.unable_to_inspect"
    classification = contract["finding_classification"]
    assert classification["machine_buckets"] == ["defect", "suggestion", "question"]
    assert classification["portable_entry_fields"] == ["id", "category", "summary", "evidence"]
    assert classification["typed_sources"] == {
        "defect": "findings",
        "suggestion": "portable_suggestions",
        "question": "portable_questions",
    }
    assert classification["non_defect_source_phase"] == "phase_2_coverage_review"
    assert classification["non_defect_pre_id_fields"] == ["summary", "evidence"]
    assert classification["prose_only_without_concrete_evidence_is_not_portable"] is True
    assert classification["prr_metadata_outside_portable_entry"] is True

    complete_requires = contract["inspection_status"]["complete_requires"]
    assert "every_triggered_surface_status_complete" in complete_requires
    assert "no_triggered_surface_pending_unable_or_not_applicable" in complete_requires
    assert contract["change_identity"]["produced_by"] == "phase_1_2_coverage"
    assert contract["review_evidence"]["produced_by"] == "phase_2_evidence"


def test_portable_review_mode_mapping_does_not_leak_lifecycle_modes():
    contract = _yaml("pr-review/reference/review-coverage-contract.yaml")
    mapping = contract["review_evidence"]["portable_review_mode_mapping"]
    assert mapping["exhaustive_when"] == "user_requested_exhaustive_or_full_pass"
    assert "retrospective" in mapping["normal_when"]
    assert contract["review_evidence"]["lifecycle_metadata_outside_portable_review_mode"] == [
        "incremental",
        "retrospective",
    ]


def test_phase_index_wires_explicit_coverage_review_and_evidence_phases():
    phase_index = _text("pr-review/reference/phase-index.md")
    for token in (
        "phase-1-2-coverage.md",
        "phase-2-coverage-review.md",
        "phase-2-evidence.md",
        "review-coverage-execution.md",
        "change_identity",
        "inspection_plan",
        "review_evidence",
        "portable_suggestions",
        "portable_questions",
        "unable_to_inspect",
    ):
        assert token in phase_index


def test_coverage_execution_builds_identity_and_runs_systematic_review():
    execution = _text("pr-review/reference/review-coverage-execution.md")
    for token in (
        "phase 1→2 coverage",
        "coverage review",
        "change_identity",
        "inspection_plan",
        "hidden consumers",
        "cross-file impact",
        "schema/migration compatibility",
        "rollout/rollback",
        "test quality",
        "dependency/config/iac",
        "unable_to_inspect",
        "do not substitute or guess",
        "untrusted data",
        "finding-pipeline.md",
    ):
        assert token.lower() in execution.lower()


def test_coverage_execution_emits_shared_review_evidence_and_classifies_findings():
    execution = _text("pr-review/reference/review-coverage-execution.md")
    for token in (
        "phase 2 evidence",
        "review_evidence",
        "defect",
        "suggestion",
        "question",
        "inspection_status",
        "inspected_surfaces",
        "generated_at",
        "stale/invalid envelope blocks posting",
        "contains exactly",
        "incremental and retrospective",
        "validate_review_coverage.py",
        "validate_review_coverage(...)",
        "gate blocker",
    ):
        assert token.lower() in execution.lower()


def test_workflow_contract_sequences_batch5_2b_machine_state_phases():
    workflow = _yaml("pr-review/workflow-contract.yaml")
    for route in ("posting", "chat_only"):
        phases = workflow["routes"][route]["phases"]
        assert phases.index("1") < phases.index("1-2-coverage") < phases.index("2")
        assert phases.index("2") < phases.index("2-coverage-review") < phases.index("2-evidence")
        assert phases.index("2-evidence") < phases.index("2-3-gate")


def test_explicit_phase_contracts_produce_and_consume_machine_state():
    coverage = _text("pr-review/workflow/phase-1-2-coverage.md")
    coverage_review = _text("pr-review/workflow/phase-2-coverage-review.md")
    evidence = _text("pr-review/workflow/phase-2-evidence.md")

    for token in ("change_identity: object", "inspection_plan: object", "initial_unable_to_inspect: list"):
        assert token in coverage

    for token in (
        "inspection_plan: object",
        "coverage_unable_to_inspect: list",
        "portable_suggestions: list",
        "portable_questions: list",
        "root_cause_groups: list",
        "regenerated `root_cause_groups`",
        "≤10-row cap",
    ):
        assert token in coverage_review

    for token in (
        "review_evidence: object",
        "change_identity: object",
        "inspection_plan: object",
        "coverage_unable_to_inspect: list",
        "portable_suggestions: list",
        "portable_questions: list",
        "validate_review_coverage.py",
    ):
        assert token in evidence


def test_phase2_to_3_gate_fails_closed_on_invalid_or_incomplete_evidence():
    gate = _text("pr-review/workflow/phase-2-3-gate.md")
    for token in (
        "review_evidence",
        "change_identity",
        "inspection_plan: object",
        "inspection_status: unable",
        "posting_decision: skip",
        "pending mandatory surface",
    ):
        assert token.lower() in gate.lower()


def test_skill_definition_of_done_requires_complete_or_annotated_inspection():
    skill = _text("pr-review/SKILL.md")
    assert "review-coverage-contract.yaml" in skill
    assert "review-evidence.yaml" in skill
    assert "change-identity.yaml" in skill
    assert "unable_to_inspect" in skill
    assert "hidden consumer" in skill.lower()
    assert "dependency/config/IaC" in skill
    assert "validate_review_coverage" in skill
