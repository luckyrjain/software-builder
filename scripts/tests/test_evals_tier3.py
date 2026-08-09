"""Tests for Tier-3 golden output behavioral evals."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_golden_fixtures_load() -> None:
    from scripts.evals.golden import load_golden_fixtures

    cases = load_golden_fixtures(ROOT / "evals" / "golden")
    case_ids = {(case.skill, case.case_id) for case in cases}
    assert ("pr-review", "golden-chat-only-not-posted") in case_ids
    assert ("pr-review", "golden-injection-inert-render") in case_ids
    assert ("prd-architect", "golden-validation-no-mvp") in case_ids
    assert len(cases) == 8


def test_golden_cases_pass_on_repository() -> None:
    from scripts.evals.__main__ import run_all

    results = run_all(ROOT, tier_filter=3)
    failures = [result for result in results if not result.passed]
    assert failures == [], failures


def test_golden_forbid_field_value_detects_violation(tmp_path: Path) -> None:
    from scripts.evals.golden import GoldenCase, run_golden_case

    case = GoldenCase(
        skill="demo",
        case_id="posted-when-forbidden",
        tier=3,
        description="",
        recorded_output={"review_metadata": {"posted": True}},
        assertions=[{"type": "forbid_field_value", "path": "review_metadata.posted", "value": True}],
        path=tmp_path / "bad.yaml",
    )
    result = run_golden_case(case)
    assert not result.passed
