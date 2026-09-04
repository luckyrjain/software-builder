from __future__ import annotations

from pathlib import Path

from scripts.evals.__main__ import run_all
from scripts.evals.eval_coverage_contract import (
    REQUIRED_BEHAVIOR_SCENARIOS,
    REQUIRED_MUTATION_CLASSES,
    REQUIRED_UNTRUSTED_SURFACES,
)
from scripts.evals.golden import load_golden_fixtures
from scripts.yaml_safety import load_unique_yaml_file, require_mapping

ROOT = Path(__file__).resolve().parents[2]

# Imported above, not restated: the validator these tests mirror owns the policy,
# so `python3 -m scripts.evals` reports a gap too, and the two cannot drift.
REQUIRED_DEGRADED_HOST_CASES = {
    "missing_observability",
    "live_state_without_history",
    "scm_without_checkout",
    "local_git_without_scm",
    "missing_ci_visibility",
    "missing_issue_tracker",
    "missing_subagents",
}
REQUIRED_ROUTING_COLLISIONS = {
    "architecture-vs-code-review",
    "prd-vs-code-review",
    "pr-number-review",
    "prod-failure-vs-sizing",
    "resource-safety-vs-incident",
    "write-tests-vs-test-review",
    "current-state-before-change",
    "numbered-pr-change-impact",
    "numbered-pr-change-impact-vs-deployment-risk",
    "numbered-pr-production-readiness",
    "numbered-pr-ready-to-release-vs-release-wide",
    "release-wide-go-no-go-vs-production-readiness",
}


def _contract() -> dict:
    raw = load_unique_yaml_file(ROOT / "scripts" / "registry" / "eval_contracts.yaml")
    return require_mapping(raw, "eval contracts")


def test_behavior_scenario_matrix_is_complete_and_executable() -> None:
    contract = _contract()
    scenarios = require_mapping(contract.get("behavior_scenarios"), "behavior_scenarios")
    assert set(scenarios) == REQUIRED_BEHAVIOR_SCENARIOS

    golden = load_golden_fixtures(ROOT / "evals" / "golden")
    results = run_all(ROOT, golden_cases=golden)
    result_map = {f"{result.skill}/{result.case_id}": result for result in results}
    for scenario_id, raw in scenarios.items():
        config = require_mapping(raw, f"behavior_scenarios.{scenario_id}")
        refs = config.get("case_refs", [])
        gate = config.get("contract_gate")
        assert bool(refs) ^ bool(gate), f"{scenario_id}: declare exactly one of case_refs or contract_gate"
        if refs:
            assert isinstance(refs, list) and all(isinstance(ref, str) and ref for ref in refs)
            for ref in refs:
                assert ref in result_map, f"{scenario_id}: missing eval result {ref}"
                assert result_map[ref].passed, f"{scenario_id}: eval result is failing: {ref}"
        if gate == "routing_collisions":
            routing = [result for key, result in result_map.items() if key.startswith("batch3/routing-collision-suite")]
            assert routing and all(result.passed for result in routing)
        elif gate == "adversarial_matrix":
            adversarial = [
                result
                for key, result in result_map.items()
                if key.startswith("batch3-mutation/")
            ]
            assert adversarial and all(result.passed for result in adversarial)
        elif gate is not None:
            raise AssertionError(f"{scenario_id}: unknown contract_gate {gate!r}")


def test_adversarial_and_surface_matrices_are_complete() -> None:
    contract = _contract()
    mutations = require_mapping(contract.get("adversarial_classes"), "adversarial_classes")
    surfaces = require_mapping(contract.get("untrusted_surfaces"), "untrusted_surfaces")
    assert set(mutations) == REQUIRED_MUTATION_CLASSES
    assert set(surfaces) == REQUIRED_UNTRUSTED_SURFACES


def test_degraded_host_matrix_is_complete() -> None:
    contract = _contract()
    degraded = require_mapping(contract.get("degraded_host_cases"), "degraded_host_cases")
    assert set(degraded) == REQUIRED_DEGRADED_HOST_CASES


def test_routing_collision_matrix_is_complete() -> None:
    contract = _contract()
    collisions = contract.get("routing_collisions")
    assert isinstance(collisions, list)
    ids = {str(item.get("id")) for item in collisions if isinstance(item, dict)}
    assert ids == REQUIRED_ROUTING_COLLISIONS
    assert len(collisions) == len(REQUIRED_ROUTING_COLLISIONS)
