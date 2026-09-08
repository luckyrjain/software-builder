from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[2]
SURFACES = (
    "cross_file_impact",
    "hidden_consumers",
    "schema_migration_compatibility",
    "rollout_rollback",
    "test_quality",
    "dependency_config_iac",
)


def _load_validator():
    path = ROOT / "pr-review/scripts/validate_review_coverage.py"
    spec = importlib.util.spec_from_file_location("validate_review_coverage", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _identity():
    return {
        "schema_version": 1,
        "base_sha": "a" * 40,
        "head_sha": "b" * 40,
        "merge_base_sha": "a" * 40,
        "normalized_diff_fingerprint": "c" * 64,
        "changed_paths": ["src/a.py"],
        "generated_paths": [],
        "dependency_changes": [],
        "config_changes": [],
    }


def _plan():
    return {
        surface: {
            "triggered": True,
            "reason": "test trigger",
            "mandatory": True,
            "evidence_sources": [f"diff:{surface}"],
            "status": "complete",
        }
        for surface in SURFACES
    }


def _evidence(findings):
    return {
        "schema_version": 1,
        "change_identity": _identity(),
        "requirements_ref": None,
        "review_mode": "normal",
        "inspection_status": "complete",
        "inspected_surfaces": list(SURFACES),
        "unable_to_inspect": [],
        "findings": findings,
        "generated_at": "2026-08-19T00:00:00Z",
    }


def test_unsorted_suggestion_evidence_fails_closed_even_with_matching_id():
    validator = _load_validator()
    evidence = "tests/test_a.py:8; src/a.py:12"
    finding_id = validator._content_finding_id("suggestion", "Add coverage", evidence)
    findings = {
        "defect": [],
        "suggestion": [
            {"id": finding_id, "category": "suggestion", "summary": "Add coverage", "evidence": evidence}
        ],
        "question": [],
    }
    errors = validator.validate_review_coverage(_plan(), _evidence(findings), current_identity=_identity())
    assert any("stable sorted unique refs" in error for error in errors)


def test_canonical_surface_reason_question_evidence_remains_valid():
    validator = _load_validator()
    evidence = "surface:hidden_consumers; reason:registry unavailable"
    finding_id = validator._content_finding_id("question", "Who owns this consumer?", evidence)
    findings = {
        "defect": [],
        "suggestion": [],
        "question": [
            {"id": finding_id, "category": "question", "summary": "Who owns this consumer?", "evidence": evidence}
        ],
    }
    assert validator.validate_review_coverage(_plan(), _evidence(findings), current_identity=_identity()) == []
