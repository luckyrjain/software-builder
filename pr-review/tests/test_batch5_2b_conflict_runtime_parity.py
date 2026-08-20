from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
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


def _evidence():
    return {
        "schema_version": 1,
        "change_identity": _identity(),
        "requirements_ref": None,
        "review_mode": "normal",
        "inspection_status": "complete",
        "inspected_surfaces": ["cross_file_impact"],
        "unable_to_inspect": [],
        "findings": {"defect": [], "suggestion": [], "question": []},
        "generated_at": "2026-08-19T00:00:00Z",
    }


def test_runtime_and_repo_validator_agree_conflict_resolution_invalidates_evidence():
    repo = _load(ROOT / "scripts/validate_review_contracts.py", "repo_review_validator_conflict")
    runtime = _load(
        ROOT / "docs/skill-framework/shared/review_contract_runtime.py",
        "runtime_review_validator_conflict",
    )
    kwargs = {
        "current_identity": _identity(),
        "conflict_resolution_occurred": True,
    }
    repo_errors = repo.validate_review_evidence(_evidence(), **kwargs)
    runtime_errors = runtime.validate_review_evidence(_evidence(), **kwargs)
    assert runtime_errors == repo_errors
    assert any("stale change_identity" in error for error in runtime_errors)
