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
