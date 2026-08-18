from pathlib import Path
import importlib.util

import yaml

ROOT = Path(__file__).resolve().parents[2]


def _load_validator():
    path = ROOT / "scripts/validate_review_contracts.py"
    spec = importlib.util.spec_from_file_location("validate_review_contracts_closed_docs", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _yaml(path: str):
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def _write_contracts(tmp_path, change, evidence):
    shared = tmp_path / "docs/skill-framework/shared"
    shared.mkdir(parents=True)
    (shared / "change-identity.yaml").write_text(yaml.safe_dump(change), encoding="utf-8")
    (shared / "review-evidence.yaml").write_text(yaml.safe_dump(evidence), encoding="utf-8")


def test_contract_documents_reject_unknown_top_level_fields(tmp_path):
    validator = _load_validator()
    change = _yaml("docs/skill-framework/shared/change-identity.yaml")
    evidence = _yaml("docs/skill-framework/shared/review-evidence.yaml")
    change["future_contract_field"] = True
    evidence["future_contract_field"] = True
    _write_contracts(tmp_path, change, evidence)
    errors = validator.validate_contract_documents(tmp_path)
    assert any("change identity contract top-level fields drifted" in error for error in errors)
    assert any("review evidence contract top-level fields drifted" in error for error in errors)


def test_contract_documents_reject_unknown_spec_fields(tmp_path):
    validator = _load_validator()
    change = _yaml("docs/skill-framework/shared/change-identity.yaml")
    evidence = _yaml("docs/skill-framework/shared/review-evidence.yaml")
    change["change_identity"]["future_semantic"] = True
    evidence["review_evidence"]["future_semantic"] = True
    _write_contracts(tmp_path, change, evidence)
    errors = validator.validate_contract_documents(tmp_path)
    assert any("change identity contract spec fields drifted" in error for error in errors)
    assert any("review evidence contract spec fields drifted" in error for error in errors)
