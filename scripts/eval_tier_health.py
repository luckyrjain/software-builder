#!/usr/bin/env python3
"""Deterministic eval-tier coverage for the Batch 5 prompt-system health report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from scripts.evals.__main__ import load_fixtures
from scripts.evals.golden import load_golden_fixtures
from scripts.evals.transcript import load_transcript_fixtures
from scripts.registry.schema import parse_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[1]


def build_eval_tier_health(root: Path = ROOT) -> dict[str, Any]:
    registry = parse_registry(root / "skills.yaml")

    tier1 = len(load_fixtures(root / "evals" / "fixtures"))
    global_fixture = root / "evals" / "fixtures" / "_global.yaml"
    if global_fixture.is_file():
        global_raw = load_unique_yaml_file(global_fixture)
        if isinstance(global_raw, dict):
            templates = sum(
                1
                for name in ("happy", "adversarial")
                if isinstance(global_raw.get(name), dict)
            )
            tier1 += templates * len(registry.skills)

    tier2 = len(load_transcript_fixtures(root / "evals" / "transcripts"))
    tier3 = len(load_golden_fixtures(root / "evals" / "golden"))
    tiers = {
        "tier_1_structural": tier1,
        "tier_2_transcript": tier2,
        "tier_3_golden": tier3,
    }
    return {
        "tiers": tiers,
        "covered_tiers": sum(1 for count in tiers.values() if count > 0),
        "required_tiers": len(tiers),
        "live_model_harness": {
            "available": (root / "scripts" / "evals" / "live_harness.py").is_file(),
            "ci_blocking": False,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    tiers = report["tiers"]
    live = report["live_model_harness"]
    return "\n".join(
        [
            "### Eval tier coverage",
            "",
            f"- Tier 1 structural cases: **{tiers['tier_1_structural']}**",
            f"- Tier 2 transcript cases: **{tiers['tier_2_transcript']}**",
            f"- Tier 3 golden cases: **{tiers['tier_3_golden']}**",
            f"- Deterministic tiers covered: **{report['covered_tiers']}/{report['required_tiers']}**",
            f"- Live model harness: **{'available' if live['available'] else 'missing'}** (non-blocking)",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    report = build_eval_tier_health()
    if report["covered_tiers"] != report["required_tiers"] or not report["live_model_harness"]["available"]:
        print(render_markdown(report) if args.format == "markdown" else json.dumps(report, sort_keys=True, indent=2))
        return 1
    print(render_markdown(report) if args.format == "markdown" else json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
