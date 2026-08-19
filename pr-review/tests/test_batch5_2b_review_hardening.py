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
    assert contract["finding_classification"]["machine_buckets"] == ["defect", "suggestion", "question"]


def test_phase1_builds_change_identity_and_inspection_plan():
    phase1 = _text("pr-review/workflow/phase-1.md")
    for token in (
        "change_identity",
        "inspection_plan",
        "review-coverage-contract.yaml",
        "hidden consumers",
        "dependency/config/IaC",
        "unable_to_inspect",
    ):
        assert token.lower() in phase1.lower()


def test_phase2_emits_shared_review_evidence_and_classifies_findings():
    phase2 = _text("pr-review/workflow/phase-2.md")
    for token in (
        "review_evidence",
        "defect",
        "suggestion",
        "question",
        "unable_to_inspect",
        "inspection_status",
        "cross-file impact",
        "schema/migration compatibility",
        "hidden consumers",
        "dependency/config/IaC",
    ):
        assert token.lower() in phase2.lower()


def test_workflow_contract_carries_batch5_2b_machine_state():
    workflow = _yaml("pr-review/workflow-contract.yaml")
    assert "review_evidence" in workflow["routes"]["posting"].get("required_outputs", [])
    assert "review_evidence" in workflow["routes"]["chat_only"].get("required_outputs", [])


def test_skill_definition_of_done_requires_complete_or_annotated_inspection():
    skill = _text("pr-review/SKILL.md")
    assert "review-coverage-contract.yaml" in skill
    assert "review-evidence.yaml" in skill
    assert "change-identity.yaml" in skill
    assert "unable_to_inspect" in skill
    assert "hidden consumer" in skill.lower()
