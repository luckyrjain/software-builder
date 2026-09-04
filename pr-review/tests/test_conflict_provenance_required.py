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


def _identity(base="a", merge_base="a"):
    return {
        "schema_version": 1,
        "base_sha": base * 40,
        "head_sha": "b" * 40,
        "merge_base_sha": merge_base * 40,
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


def _evidence():
    return {
        "schema_version": 1,
        "change_identity": _identity(),
        "requirements_ref": None,
        "review_mode": "normal",
        "inspection_status": "complete",
        "inspected_surfaces": list(SURFACES),
        "unable_to_inspect": [],
        "findings": {"defect": [], "suggestion": [], "question": []},
        "generated_at": "2026-08-19T00:00:00Z",
    }


def test_sha_transition_requires_explicit_conflict_resolution_provenance():
    validator = _load_validator()
    current = _identity(base="d", merge_base="d")
    errors = validator.validate_review_coverage(_plan(), _evidence(), current_identity=current)
    assert any("conflict_resolution_occurred must be established" in error for error in errors)


def test_verified_no_conflict_allows_content_neutral_synced_base_update():
    validator = _load_validator()
    current = _identity(base="d", merge_base="d")
    assert validator.validate_review_coverage(
        _plan(),
        _evidence(),
        current_identity=current,
        conflict_resolution_occurred=False,
    ) == []
