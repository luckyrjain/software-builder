from __future__ import annotations

from scripts.eval_tier_health import build_eval_tier_health, render_markdown


def test_eval_tier_health_covers_all_deterministic_tiers() -> None:
    report = build_eval_tier_health()

    assert report["required_tiers"] == 3
    assert report["covered_tiers"] == 3
    assert set(report["tiers"]) == {
        "tier_1_structural",
        "tier_2_transcript",
        "tier_3_golden",
    }
    assert all(count > 0 for count in report["tiers"].values())
    assert report["live_model_harness"] == {
        "available": True,
        "ci_blocking": False,
    }


def test_eval_tier_health_markdown_is_deterministic_and_explicit() -> None:
    report = build_eval_tier_health()

    first = render_markdown(report)
    second = render_markdown(report)

    assert first == second
    assert "### Eval tier coverage" in first
    assert "Tier 1 structural cases" in first
    assert "Tier 2 transcript cases" in first
    assert "Tier 3 golden cases" in first
    assert "Deterministic tiers covered: **3/3**" in first
    assert "Live model harness: **available** (non-blocking)" in first
