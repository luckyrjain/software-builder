from __future__ import annotations

from pathlib import Path

from scripts.evals.golden import load_golden_fixtures
from scripts.evals.mutation_guard import run_guardrail_mutation_checks

ROOT = Path(__file__).resolve().parents[2]


def test_all_guardrail_mutations_remain_inert_and_fail_when_compromised() -> None:
    golden = load_golden_fixtures(ROOT / "evals" / "golden")
    results = run_guardrail_mutation_checks(ROOT, golden)

    assert {result.case_id for result in results} == {
        "instruction_override",
        "gate_bypass",
        "security_gate_bypass",
        "confidence_forcing",
        "unauthorized_external_action",
        "merge_forcing",
    }
    assert all(result.passed for result in results), [
        (result.case_id, result.messages) for result in results if not result.passed
    ]


def test_guardrail_mutation_checks_run_through_the_real_eval_cli() -> None:
    """The dynamic mutate-and-reassert proof must be reachable via `python -m
    scripts.evals`, not just callable directly -- otherwise a CI pipeline that
    only runs the eval CLI (not pytest) never executes it at all."""
    from scripts.evals.__main__ import run_all

    results = run_all(ROOT)
    mutation_results = [result for result in results if result.skill == "batch3-mutation"]

    assert {result.case_id for result in mutation_results} == {
        "instruction_override",
        "gate_bypass",
        "security_gate_bypass",
        "confidence_forcing",
        "unauthorized_external_action",
        "merge_forcing",
    }
    assert all(result.passed for result in mutation_results), [
        (result.case_id, result.messages) for result in mutation_results if not result.passed
    ]
