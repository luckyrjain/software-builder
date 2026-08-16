#!/usr/bin/env python3
"""Deterministic eval-tier coverage for the Batch 5 prompt-system health report."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.evals.__main__ import load_fixtures
from scripts.evals.golden import load_golden_fixtures
from scripts.evals.transcript import load_transcript_fixtures
from scripts.registry.schema import parse_registry
from scripts.yaml_safety import load_unique_yaml_file

EXPECTED_TIERS = {1, 2, 3}


def build_eval_tier_health(root: Path = ROOT) -> dict[str, Any]:
    registry = parse_registry(root / "skills.yaml")
    counts: Counter[int] = Counter()

    for case in load_fixtures(root / "evals" / "fixtures"):
        counts[case.tier] += 1

    global_fixture = root / "evals" / "fixtures" / "_global.yaml"
    if global_fixture.is_file():
        global_raw = load_unique_yaml_file(global_fixture)
        if isinstance(global_raw, dict):
            for name in ("happy", "adversarial"):
                template = global_raw.get(name)
                if isinstance(template, dict):
                    counts[int(template.get("tier", 1))] += len(registry.skills)

    for case in load_transcript_fixtures(root / "evals" / "transcripts"):
        counts[case.tier] += 1
    for case in load_golden_fixtures(root / "evals" / "golden"):
        counts[case.tier] += 1

    tiers = {
        "tier_1_structural": counts[1],
        "tier_2_transcript": counts[2],
        "tier_3_golden": counts[3],
    }
    unexpected = {str(tier): count for tier, count in sorted(counts.items()) if tier not in EXPECTED_TIERS}
    return {
        "tiers": tiers,
        "covered_tiers": sum(1 for count in tiers.values() if count > 0),
        "required_tiers": len(tiers),
        "unexpected_static_tiers": unexpected,
        "live_model_harness": {
            "available": (root / "scripts" / "evals" / "live_harness.py").is_file(),
            "ci_blocking": False,
        },
    }


def is_healthy(report: dict[str, Any]) -> bool:
    """Return deterministic CI health; the live model harness is visibility-only."""
    return (
        report["covered_tiers"] == report["required_tiers"]
        and not report["unexpected_static_tiers"]
    )


def render_markdown(report: dict[str, Any]) -> str:
    tiers = report["tiers"]
    live = report["live_model_harness"]
    unexpected = report["unexpected_static_tiers"]
    return "\n".join(
        [
            "### Eval tier coverage",
            "",
            f"- Tier 1 structural cases: **{tiers['tier_1_structural']}**",
            f"- Tier 2 transcript cases: **{tiers['tier_2_transcript']}**",
            f"- Tier 3 golden cases: **{tiers['tier_3_golden']}**",
            f"- Deterministic tiers covered: **{report['covered_tiers']}/{report['required_tiers']}**",
            f"- Unexpected static tiers: **{len(unexpected)}**",
            f"- Live model harness: **{'available' if live['available'] else 'missing'}** (non-blocking)",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    report = build_eval_tier_health()
    print(render_markdown(report) if args.format == "markdown" else json.dumps(report, sort_keys=True, indent=2))
    return 0 if is_healthy(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())