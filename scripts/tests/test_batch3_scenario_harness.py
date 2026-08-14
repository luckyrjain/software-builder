from __future__ import annotations

from pathlib import Path

from scripts.evals.dispatcher import dispatch_prompt
from scripts.evals.scenario_harness import DIMENSIONS, run_per_skill_scenarios
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


def test_literal_dimension_directories_cover_every_skill() -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    results = run_per_skill_scenarios(ROOT, registry)
    assert len(results) == len(registry.skills) * len(DIMENSIONS) == 115
    assert all(result.passed for result in results), [
        (result.skill, result.case_id, result.messages) for result in results if not result.passed
    ]
    for dimension in DIMENSIONS:
        assert (ROOT / "evals" / dimension / "cases.yaml").is_file()
        assert sum(result.case_id == f"scenario-{dimension}" for result in results) == len(registry.skills)


def test_collision_prompts_execute_dispatcher_not_markdown_regex_only() -> None:
    from scripts.yaml_safety import load_unique_yaml_file

    registry = parse_registry(ROOT / "skills.yaml")
    contract = load_unique_yaml_file(ROOT / "scripts" / "registry" / "eval_contracts.yaml")
    collisions = contract["routing_collisions"]
    for case in collisions:
        result = dispatch_prompt(ROOT, registry, case["prompt"])
        assert result.status == "selected", (case["id"], result)
        assert result.owner == case["expected_owner"], (case["id"], result)


def test_degraded_policy_is_explicit_for_every_registered_skill() -> None:
    from scripts.yaml_safety import load_unique_yaml_file

    registry = parse_registry(ROOT / "skills.yaml")
    policy = load_unique_yaml_file(ROOT / "scripts" / "registry" / "degraded_behavior.yaml")
    assert set(policy["skills"]) == set(registry.skills)
    assert all(config["behavior"] in {"BLOCKED", "DEGRADED", "FALLBACK"} for config in policy["skills"].values())
