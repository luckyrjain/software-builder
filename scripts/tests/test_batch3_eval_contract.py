from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from scripts.evals.__main__ import run_all
from scripts.evals.batch3_contract import REQUIRED_DIMENSIONS, run_batch3_contract_checks
from scripts.evals.golden import load_golden_fixtures
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


def _mutation_results(case_results):
    return [result for result in case_results if result.skill == "batch3-mutation"]


@lru_cache(maxsize=1)
def _baseline():
    registry = parse_registry(ROOT / "skills.yaml")
    golden = load_golden_fixtures(ROOT / "evals" / "golden")
    results = run_all(ROOT, golden_cases=golden)
    return registry, golden, results


def test_batch3_all_registered_skills_execute_five_scenarios() -> None:
    registry, _golden, results = _baseline()
    scenario_results = [
        result
        for result in results
        if result.skill in registry.skills and result.case_id.startswith("scenario-")
    ]
    assert len(scenario_results) == len(registry.skills) * len(REQUIRED_DIMENSIONS)
    assert {result.case_id for result in scenario_results} == {
        f"scenario-{dimension}" for dimension in REQUIRED_DIMENSIONS
    }
    assert all(result.passed for result in scenario_results), [
        (result.skill, result.case_id, result.messages) for result in scenario_results if not result.passed
    ]


def test_batch3_repository_matrices_and_golden_coverage_pass() -> None:
    registry, golden, results = _baseline()
    checks = run_batch3_contract_checks(
        ROOT,
        registry,
        case_results=results,
        mutation_results=_mutation_results(results),
        golden_cases=golden,
    )
    assert {result.case_id for result in checks} == {
        "all-skill-five-dimension-scenarios",
        "all-skill-golden",
        "behavior-scenario-matrix",
        "routing-collision-suite",
        "mutation-matrix",
        "mutation-anchor-matrix",
        "untrusted-surface-matrix",
        "degraded-host-matrix",
    }
    assert all(result.passed for result in checks), [
        (result.case_id, result.messages) for result in checks if not result.passed
    ]


def test_batch3_scenario_gate_fails_when_one_skill_loses_a_dimension() -> None:
    registry, golden, results = _baseline()
    filtered = [
        result
        for result in results
        if not (result.skill == "pr-review" and result.case_id == "scenario-degraded")
    ]
    checks = run_batch3_contract_checks(
        ROOT,
        registry,
        case_results=filtered,
        mutation_results=_mutation_results(filtered),
        golden_cases=golden,
    )
    gate = next(result for result in checks if result.case_id == "all-skill-five-dimension-scenarios")
    assert not gate.passed
    assert any("pr-review: missing executable degraded scenario" in message for message in gate.messages)


def test_batch3_golden_gate_fails_when_a_skill_loses_all_golden_coverage() -> None:
    registry, golden, results = _baseline()
    reduced = [case for case in golden if case.skill != "pr-review"]
    checks = run_batch3_contract_checks(
        ROOT,
        registry,
        case_results=results,
        mutation_results=_mutation_results(results),
        golden_cases=reduced,
    )
    gate = next(result for result in checks if result.case_id == "all-skill-golden")
    assert not gate.passed
    assert any("pr-review: no golden fixture" in message for message in gate.messages)


def test_batch3_mutation_gate_fails_when_executable_mutation_is_missing() -> None:
    registry, golden, results = _baseline()
    filtered = [
        result
        for result in results
        if not (result.skill == "batch3-mutation" and result.case_id == "unauthorized_external_action")
    ]
    checks = run_batch3_contract_checks(
        ROOT,
        registry,
        case_results=filtered,
        mutation_results=_mutation_results(filtered),
        golden_cases=golden,
    )
    gate = next(result for result in checks if result.case_id == "mutation-matrix")
    assert not gate.passed
    assert any("batch3-mutation/unauthorized_external_action" in message for message in gate.messages)


def test_batch3_mutation_anchor_requires_passing_dangerous_fixture() -> None:
    registry, golden, results = _baseline()
    filtered = [
        result
        for result in results
        if not (result.skill == "pr-review" and result.case_id == "golden-injection-inert-render")
    ]
    checks = run_batch3_contract_checks(
        ROOT,
        registry,
        case_results=filtered,
        mutation_results=_mutation_results(filtered),
        golden_cases=golden,
    )
    gate = next(result for result in checks if result.case_id == "mutation-anchor-matrix")
    assert not gate.passed
    assert any("pr-review/golden-injection-inert-render" in message for message in gate.messages)


def test_batch3_mutation_matrix_does_not_depend_on_case_results_order() -> None:
    # Regression test for 80e588a ("dedupe mutation evals"): mutation-matrix must pass off the
    # explicit mutation_results argument alone, not off case_results having already been merged
    # with them in the right order. case_results here deliberately omits every batch3-mutation/*
    # entry -- if mutation-matrix silently fell back to reading them out of case_results, this
    # would wrongly fail with "missing executable mutation result".
    registry, golden, results = _baseline()
    mutation_results = _mutation_results(results)
    case_results_without_mutations = [
        result for result in results if result.skill != "batch3-mutation"
    ]
    checks = run_batch3_contract_checks(
        ROOT,
        registry,
        case_results=case_results_without_mutations,
        mutation_results=mutation_results,
        golden_cases=golden,
    )
    gate = next(result for result in checks if result.case_id == "mutation-matrix")
    assert gate.passed, gate.messages
