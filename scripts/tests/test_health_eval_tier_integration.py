from __future__ import annotations

from scripts.operational_upkeep import build_health_report, render_health_markdown


def test_health_report_contains_eval_tier_snapshot() -> None:
    report = build_health_report(revision="deadbeef")
    eval_tiers = report["health"]["eval_tiers"]

    assert eval_tiers["covered_tiers"] == eval_tiers["required_tiers"] == 3
    assert eval_tiers["tiers"]["tier_1_structural"] > 0
    assert eval_tiers["tiers"]["tier_2_transcript"] > 0
    assert eval_tiers["tiers"]["tier_3_golden"] > 0
    assert eval_tiers["unexpected_static_tiers"] == {}
    assert eval_tiers["live_model_harness"]["available"] is True

    markdown = render_health_markdown(report)
    assert "Eval tiers: **3/3 covered**" in markdown
    assert "Unexpected static eval tiers: **0**" in markdown
    assert "Live model harness: **available**" in markdown
