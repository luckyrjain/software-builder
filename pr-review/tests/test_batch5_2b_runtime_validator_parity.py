"""The repository entry point and the vendored runtime are one implementation, not a fork.

These used to be example-based parity tests over hand-picked envelopes: two independent copies of
the validators, sampled at a handful of inputs, so any divergence outside those samples shipped
silently. scripts/validate_review_contracts.py now loads the vendored runtime instead of
re-implementing it, so parity is structural. What is worth pinning is that the inversion stays --
that the repo-side module keeps exposing the validators and keeps sourcing them from the file
installed packages actually execute.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "docs/skill-framework/shared/review_contract_runtime.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repo_validator_entry_points_are_the_vendored_runtimes_own_functions():
    repo = _load(ROOT / "scripts/validate_review_contracts.py", "repo_review_validator")

    assert Path(repo.shared_runtime.__file__).resolve() == RUNTIME.resolve()
    assert repo.validate_review_evidence is repo.shared_runtime.validate_review_evidence
    assert repo.validate_change_identity is repo.shared_runtime.validate_change_identity


def test_repo_validator_does_not_redefine_the_shared_validators():
    source = (ROOT / "scripts/validate_review_contracts.py").read_text(encoding="utf-8")

    assert "def validate_review_evidence(" not in source
    assert "def validate_change_identity(" not in source
    # The repo-side extras that are genuinely repository-only stay here.
    assert "def validate_contract_documents(" in source


def test_contract_documents_are_checked_against_the_runtimes_own_field_vocabulary():
    repo = _load(ROOT / "scripts/validate_review_contracts.py", "repo_review_validator_fields")
    runtime = _load(RUNTIME, "runtime_review_validator_fields")

    assert repo._REQUIRED_IDENTITY == runtime.REQUIRED_IDENTITY_FIELDS
    assert repo._REQUIRED_EVIDENCE == runtime.REQUIRED_EVIDENCE_FIELDS
    assert repo.validate_contract_documents(ROOT) == []
