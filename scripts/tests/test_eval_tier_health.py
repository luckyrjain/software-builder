from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from scripts.eval_tier_health import build_eval_tier_health, is_healthy, render_markdown

ROOT = Path(__file__).resolve().parents[2]


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
    assert report["unexpected_static_tiers"] == {}
    assert report["live_model_harness"] == {
        "available": True,
        "ci_blocking": False,
    }
    assert is_healthy(report) is True


def test_missing_live_harness_does_not_fail_deterministic_health() -> None:
    report = build_eval_tier_health()
    report["live_model_harness"] = {"available": False, "ci_blocking": False}

    assert is_healthy(report) is True
    assert "Live model harness: **missing** (non-blocking)" in render_markdown(report)


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
    assert "Unexpected static tiers: **0**" in first
    assert "Live model harness: **available** (non-blocking)" in first


def test_eval_tier_health_cli_runs_from_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/eval_tier_health.py", "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert '"covered_tiers": 3' in result.stdout
    assert '"unexpected_static_tiers": {}' in result.stdout
