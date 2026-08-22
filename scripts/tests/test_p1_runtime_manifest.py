from __future__ import annotations

from pathlib import Path

from scripts.registry.crosscheck import validate_registry
from scripts.registry.p1_validation import PERMISSION_FIELDS, validate_p1_contracts
from scripts.registry.runtime_manifest import P1_CONTRACT_KEYS, build_runtime_manifest

ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SKILL_COUNT = 34


def test_runtime_manifest_exposes_all_p1_contracts() -> None:
    manifest = build_runtime_manifest(ROOT)
    contracts = manifest["contracts"]
    assert set(P1_CONTRACT_KEYS).issubset(contracts)
    assert contracts["execution_context"]["default_max_depth"] == 3
    assert contracts["input_resolution"]["order"][0] == "supplied_facts"
    assert contracts["artifact_ownership"]["consumers_may_silently_rewrite"] is False


def test_batch1_all_skills_validate_against_one_manifest() -> None:
    assert validate_registry(ROOT) == []
    assert validate_p1_contracts(ROOT) == []
    manifest = build_runtime_manifest(ROOT)
    skills = manifest["skills"]
    assert len(skills) == EXPECTED_SKILL_COUNT

    for skill_id, skill in skills.items():
        assert set(skill["permissions"]) == PERMISSION_FIELDS, skill_id
        for dependency in skill["dependencies"]:
            assert dependency in skills, (skill_id, dependency)
        for target in skill["composition"]["invokes"]:
            assert target in skills, (skill_id, target)
        for target in skill["composition"]["escalation_targets"]:
            assert target in skills, (skill_id, target)


def test_batch1_permissions_match_high_impact_classes() -> None:
    skills = build_runtime_manifest(ROOT)["skills"]
    for skill_id, skill in skills.items():
        permissions = skill["permissions"]
        risks = set(skill["risk_class"])
        assert (permissions["repository"] == "write") == (
            "repository-write" in risks or "merge" in risks
        ), skill_id
        assert permissions["unattended"] == ("unattended" in risks), skill_id
        assert permissions["merge"] == ("merge" in risks), skill_id
        if "posting" in risks:
            assert permissions["external_actions"] == "write", skill_id
