from datetime import date
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[2]


def _load_validator():
    path = ROOT / "scripts/validate_review_contracts.py"
    spec = importlib.util.spec_from_file_location("validate_review_contracts_adversarial", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity(**overrides):
    value = {
        "schema_version": 1,
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "merge_base_sha": "a" * 40,
        "normalized_diff_fingerprint": "c" * 64,
        "changed_paths": ["generated/client.py", "src/a.py"],
        "generated_paths": ["generated/client.py"],
        "dependency_changes": [],
        "config_changes": [],
    }
    value.update(overrides)
    return value


def _evidence(**overrides):
    value = {
        "schema_version": 1,
        "change_identity": _identity(),
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


def test_uppercase_sha_and_fingerprint_are_not_canonical():
    validator = _load_validator()
    errors = validator.validate_change_identity(
        _identity(base_sha="A" * 40, normalized_diff_fingerprint="C" * 64)
    )
    assert any("lowercase" in error and "base_sha" in error for error in errors)
    assert any("lowercase" in error and "normalized_diff_fingerprint" in error for error in errors)


def test_dependency_and_config_changes_reject_nonportable_values():
    validator = _load_validator()
    errors = validator.validate_change_identity(
        _identity(
            dependency_changes=[{"name": {"not", "portable"}}],
            config_changes=[{"value": float("nan")}],
        )
    )
    assert sum("JSON-portable" in error for error in errors) == 2


def test_dependency_and_config_changes_require_canonical_list_order_and_uniqueness():
    validator = _load_validator()
    errors = validator.validate_change_identity(
        _identity(
            dependency_changes=[{"name": "z"}, {"name": "a"}],
            config_changes=[{"name": "same"}, {"name": "same"}],
        )
    )
    assert any("dependency_changes must use canonical object ordering" in error for error in errors)
    assert any("config_changes must use canonical object ordering" in error for error in errors)


def test_requirements_ref_rejects_yaml_specific_nonportable_values():
    validator = _load_validator()
    errors = validator.validate_review_evidence(
        _evidence(requirements_ref={"as_of": date(2026, 8, 18)})
    )
    assert any("requirements_ref" in error and "JSON-portable" in error for error in errors)


def test_requirements_freshness_distinguishes_boolean_from_integer():
    validator = _load_validator()
    errors = validator.validate_review_evidence(
        _evidence(requirements_ref={"revision": True}),
        current_identity=_identity(),
        current_requirements_ref={"revision": 1},
    )
    assert any("stale requirements_ref" in error for error in errors)


def test_effective_patch_freshness_distinguishes_boolean_from_integer():
    validator = _load_validator()
    stored = _identity(config_changes=[{"enabled": True}])
    current = _identity(config_changes=[{"enabled": 1}])
    errors = validator.validate_review_evidence(
        _evidence(change_identity=stored),
        current_identity=current,
    )
    assert any("stale change_identity" in error for error in errors)


def test_question_cannot_smuggle_blocking_extension_field():
    validator = _load_validator()
    findings = {
        "defect": [],
        "suggestion": [],
        "question": [
            {
                "id": "Q-1",
                "category": "question",
                "summary": "Need confirmation",
                "evidence": "contract unclear",
                "blocking": True,
            }
        ],
    }
    errors = validator.validate_review_evidence(_evidence(findings=findings))
    assert any("must contain exactly id, category, summary, and evidence" in error for error in errors)


def test_unable_to_inspect_cannot_smuggle_unknown_fields():
    validator = _load_validator()
    errors = validator.validate_review_evidence(
        _evidence(
            inspection_status="partial",
            unable_to_inspect=[
                {
                    "surface": "consumer graph",
                    "reason": "provider unavailable",
                    "mandatory": False,
                    "ignored": True,
                }
            ],
        )
    )
    assert any("must contain exactly surface, reason, and mandatory" in error for error in errors)


def test_change_identity_rejects_unknown_v1_fields():
    validator = _load_validator()
    errors = validator.validate_change_identity(_identity(provider_hint="github"))
    assert any("unknown v1 fields" in error and "provider_hint" in error for error in errors)


def test_review_evidence_rejects_unknown_v1_fields():
    validator = _load_validator()
    errors = validator.validate_review_evidence(_evidence(blocking=True))
    assert any("unknown v1 fields" in error and "blocking" in error for error in errors)


def test_repository_path_rejects_nul_byte():
    validator = _load_validator()
    errors = validator.validate_change_identity(_identity(changed_paths=["src/a.py\x00evil"]))
    assert any("repository-relative POSIX paths" in error for error in errors)
