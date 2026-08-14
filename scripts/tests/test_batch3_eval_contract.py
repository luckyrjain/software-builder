from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from scripts.evals.__main__ import run_all
from scripts.evals.batch3_contract import REQUIRED_DIMENSIONS, run_batch3_contract_checks
from scripts.evals.golden import load_golden_fixtures
from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def _baseline():
    registry = parse_registry(ROOT / "skills.yaml")
    golden = load_golden_fixtures(ROOT / "evals" / "golden")
    results = run_all(ROOT, golden_cases=golden)
    return registry, golden, results


def test_batch3_all_registered_skills_cover_five_dimensions() -> None:
    registry, golden, results = _baseline()
    checks = run_batch3_contract_checks(
        ROOT,
        registry,
        case_results=results,
        golden_cases=golden,
    )
    per_skill = [result for result in checks if result.skill in registry.skills]
    assert len(per_skill) == len(registry.skills) * len(REQUIRED_DIMENSIONS) == 115
    assert all(result.passed for result in per_skill), [
        (result.skill, result.case_id, result.messages) for result in per_skill if not result.passed
    ]


def test_batch3_repository_matrices_and_golden_coverage_pass() -> None:
    registry, golden, results = _baseline()
    checks = run_batch3_contract_checks(
        ROOT,
        registry,
        case_results=results,
        golden_cases=golden,
    )
    repository_checks = [result for result in checks if result.skill == "batch3"]
    assert {result.case_id for result in repository_checks} == {
        "all-skill-golden",
        "routing-collision-suite",
        "mutation-matrix",
        "untrusted-surface-matrix",
        "degraded-host-matrix",
    }
    assert all(result.passed for result in repository_checks), [
        (result.case_id, result.messages) for result in repository_checks if not result.passed
    ]


def test_batch3_golden_gate_fails_when_a_skill_loses_all_golden_coverage() -> None:
    registry, golden, results = _baseline()
    reduced = [case for case in golden if case.skill != "pr-review"]
    checks = run_batch3_contract_checks(
        ROOT,
        registry,
        case_results=results,
        golden_cases=reduced,
    )
    gate = next(result for result in checks if result.case_id == "all-skill-golden")
    assert not gate.passed
    assert any("pr-review: no golden fixture" in message for message in gate.messages)


def test_batch3_mutation_gate_fails_when_referenced_regression_is_missing() -> None:
    registry, golden, results = _baseline()
    filtered = [
        result
        for result in results
        if not (result.skill == "pr-review" and result.case_id == "golden-chat-only-not-posted")
    ]
    checks = run_batch3_contract_checks(
        ROOT,
        registry,
        case_results=filtered,
        golden_cases=golden,
    )
    gate = next(result for result in checks if result.case_id == "mutation-matrix")
    assert not gate.passed
    assert any("pr-review/golden-chat-only-not-posted" in message for message in gate.messages)
