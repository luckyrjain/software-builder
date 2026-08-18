from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _yaml(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_change_identity_contract_has_required_fields():
    contract = _yaml("docs/skill-framework/shared/change-identity.yaml")
    assert contract["schema_version"] == 1
    required = contract["change_identity"]["required_fields"]
    assert required == [
        "base_sha",
        "head_sha",
        "merge_base_sha",
        "normalized_diff_fingerprint",
        "changed_paths",
        "generated_paths",
        "dependency_changes",
        "config_changes",
    ]
    assert contract["normalization"]["include_generated_paths"] is True
    assert "commit_message" in contract["normalization"]["excluded_transport_metadata"]
    assert contract["freshness"]["content_change_invalidates_review"] is True


def test_review_evidence_contract_is_portable_and_fail_closed():
    contract = _yaml("docs/skill-framework/shared/review-evidence.yaml")
    assert contract["schema_version"] == 1
    evidence = contract["review_evidence"]
    assert evidence["review_modes"] == ["normal", "exhaustive"]
    assert evidence["inspection_status_values"] == ["complete", "partial", "unable"]
    assert evidence["finding_categories"] == ["defect", "suggestion", "question"]
    assert evidence["rules"]["questions_are_non_blocking_until_promoted"] is True
    assert evidence["rules"]["complete_forbidden_with_mandatory_unable_surface"] is True
    assert evidence["rules"]["stale_change_identity_invalidates_envelope"] is True
