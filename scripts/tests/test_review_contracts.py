from pathlib import Path
import importlib.util

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _yaml(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _load_validator():
    path = ROOT / "scripts/validate_review_contracts.py"
    spec = importlib.util.spec_from_file_location("validate_review_contracts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(**overrides):
    value = {
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "merge_base_sha": "a" * 40,
        "normalized_diff_fingerprint": "c" * 64,
        "changed_paths": ["src/a.py"],
        "generated_paths": [],
        "dependency_changes": [],
        "config_changes": [],
    }
    value.update(overrides)
    return value


def _evidence(identity=None, **overrides):
    value = {
        "change_identity": identity or _identity(),
        "requirements_ref": None,
        "review_mode": "normal",
        "inspection_status": "complete",
        "inspected_surfaces": ["diff"],
        "unable_to_inspect": [],
        "findings": {"defect": [], "suggestion": [], "question": []},
        "generated_at": "2026-08-18T00:00:00Z",
    }
    value.update(overrides)
    return value


def test_change_identity_contract_has_required_fields():
    contract = _yaml("docs/skill-framework/shared/change-identity.yaml")
    assert contract["schema_version"] == 1
    required = contract["change_identity"]["required_fields"]
    assert required == [
        "base_sha", "head_sha", "merge_base_sha", "normalized_diff_fingerprint",
        "changed_paths", "generated_paths", "dependency_changes", "config_changes",
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


def test_fingerprint_is_deterministic_across_line_endings():
    validator = _load_validator()
    assert validator.normalized_diff_fingerprint("@@ x\r\n+value\r\n") == validator.normalized_diff_fingerprint("@@ x\n+value\n")
    assert validator.normalized_diff_fingerprint("@@ x\n+value\n") != validator.normalized_diff_fingerprint("@@ x\n+other\n")


def test_validator_rejects_malformed_identity_and_stale_evidence():
    validator = _load_validator()
    assert validator.validate_change_identity(_identity(head_sha=True))
    current = _identity(normalized_diff_fingerprint="d" * 64)
    errors = validator.validate_review_evidence(_evidence(), current_identity=current)
    assert any("stale change_identity" in error for error in errors)


def test_content_neutral_base_update_preserves_review_without_conflict_resolution():
    validator = _load_validator()
    current = _identity(base_sha="d" * 40, head_sha="e" * 40, merge_base_sha="d" * 40)
    assert validator.validate_review_evidence(_evidence(), current_identity=current) == []
    errors = validator.validate_review_evidence(
        _evidence(), current_identity=current, conflict_resolution_occurred=True
    )
    assert any("stale change_identity" in error for error in errors)


def test_validator_rejects_complete_with_mandatory_unable_surface():
    validator = _load_validator()
    errors = validator.validate_review_evidence(_evidence(
        unable_to_inspect=[{"surface": "direct_consumers", "reason": "provider unavailable", "mandatory": True}],
    ))
    assert any("complete" in error and "mandatory" in error for error in errors)


def test_generated_path_difference_makes_identity_stale():
    validator = _load_validator()
    stored = _identity(generated_paths=["generated/client.py"])
    current = _identity(generated_paths=["generated/client_v2.py"])
    errors = validator.validate_review_evidence(_evidence(stored), current_identity=current)
    assert any("stale change_identity" in error for error in errors)


def test_unknown_finding_bucket_is_rejected():
    validator = _load_validator()
    errors = validator.validate_review_evidence(_evidence(
        inspection_status="partial",
        inspected_surfaces=[],
        findings={"defect": [], "suggestion": [], "question": [], "blocker": []},
    ))
    assert any("finding buckets" in error for error in errors)
