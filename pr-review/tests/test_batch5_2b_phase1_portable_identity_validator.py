from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_phase1_coverage_uses_packaged_identity_validator_not_repo_root_runtime():
    text = (ROOT / "pr-review/workflow/phase-1-2-coverage.md").read_text(encoding="utf-8")
    assert "docs/skill-framework/shared/review_contract_runtime.py" in text
    assert "validate_change_identity(...)" in text
    assert "live installed workflow must not depend" in text
    assert "Invalid identity blocks Phase 2" in text
