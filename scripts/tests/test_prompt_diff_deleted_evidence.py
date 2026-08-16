from __future__ import annotations

from pathlib import Path

from scripts.operational_upkeep import load_policy, validate_diff_risk


ROOT = Path(__file__).resolve().parents[2]


def test_deleted_test_path_does_not_satisfy_high_risk_evidence_gate() -> None:
    policy = load_policy(ROOT / "scripts" / "operational_upkeep.yaml")
    changed_paths = [
        "docs/skill-framework/shared/skill-routing.md",
        "scripts/tests/test_old_routing.py",
    ]
    non_deleted_evidence_paths = ["docs/skill-framework/shared/skill-routing.md"]

    risk, errors = validate_diff_risk(
        changed_paths,
        policy,
        evidence_paths=non_deleted_evidence_paths,
    )

    assert risk == "routing"
    assert errors and "requires changed eval/test evidence" in errors[0]
