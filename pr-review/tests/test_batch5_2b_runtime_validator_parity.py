from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
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
        "changed_paths": ["src/a.py"],
        "generated_paths": [],
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
        "inspected_surfaces": ["cross_file_impact"],
        "unable_to_inspect": [],
        "findings": {"defect": [], "suggestion": [], "question": []},
        "generated_at": "2026-08-19T00:00:00Z",
    }
    value.update(overrides)
    return value


def _validators():
    repo = _load(ROOT / "scripts/validate_review_contracts.py", "repo_review_validator")
    runtime = _load(
        ROOT / "docs/skill-framework/shared/review_contract_runtime.py",
        "runtime_review_validator",
    )
    return repo, runtime


def test_runtime_validator_matches_repo_validator_for_valid_envelope():
    repo, runtime = _validators()
    evidence = _evidence()
    current = _identity()
    assert runtime.validate_review_evidence(evidence, current_identity=current) == repo.validate_review_evidence(
        evidence,
        current_identity=current,
    )


def test_runtime_validator_matches_repo_validator_for_stale_identity():
    repo, runtime = _validators()
    evidence = _evidence()
    current = _identity(normalized_diff_fingerprint="d" * 64)
    assert runtime.validate_review_evidence(evidence, current_identity=current) == repo.validate_review_evidence(
        evidence,
        current_identity=current,
    )


def test_runtime_validator_matches_repo_validator_for_closed_v1_errors():
    repo, runtime = _validators()
    evidence = _evidence(extra_field=True)
    evidence["findings"] = {
        "defect": [
            {
                "id": "PRR-API-001",
                "category": "suggestion",
                "summary": "Mismatch",
                "evidence": "src/a.py:1",
                "extra": "forbidden",
            }
        ],
        "suggestion": [],
        "question": [],
    }
    assert runtime.validate_review_evidence(evidence) == repo.validate_review_evidence(evidence)


def test_runtime_validator_matches_repo_validator_for_unable_and_requirements_errors():
    repo, runtime = _validators()
    evidence = _evidence(
        inspection_status="unable",
        unable_to_inspect=[],
        requirements_ref={"ticket": "ABC-1"},
    )
    assert runtime.validate_review_evidence(
        evidence,
        current_requirements_ref={"ticket": "ABC-2"},
    ) == repo.validate_review_evidence(
        evidence,
        current_requirements_ref={"ticket": "ABC-2"},
    )


def test_runtime_validator_matches_repo_validator_for_missing_fields():
    repo, runtime = _validators()
    evidence = _evidence()
    del evidence["schema_version"]
    del evidence["review_mode"]
    del evidence["unable_to_inspect"]
    del evidence["findings"]
    assert runtime.validate_review_evidence(evidence) == repo.validate_review_evidence(evidence)
