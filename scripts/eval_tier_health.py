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
from scripts.evals.golden import GoldenCase, load_golden_fixtures
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
                if not isinstance(template, dict):
                    continue
                # Mirror scripts.evals.__main__.run_all()'s validity check so this
                # report can't claim coverage the real eval runner wouldn't execute.
                assertions = template.get("assertions", [])
                if not isinstance(assertions, list):
                    continue
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
        # Non-fatal: see build_per_skill_golden_coverage's docstring. This
        # never affects is_healthy() -- the content-authoring fix for any
        # skill it lists is a separate, larger effort than this health check.
        "per_skill_golden_coverage": build_per_skill_golden_coverage(root),
    }


def _adversarial_golden_case_ids(root: Path) -> dict[str, str]:
    """Map skill_id -> the golden case_id evals/adversarial/cases.yaml mandates for it.

    This is the *only* place the eval contract already ties a specific golden
    (Tier-3) fixture to a specific skill and dimension: each adversarial scenario
    in evals/adversarial/cases.yaml declares a `golden_ref` of "<skill>/<case_id>",
    and scripts/evals/scenario_harness.py's `_routing_case` fails the skill's
    adversarial scenario if that referenced golden fixture is missing or failing.
    Reused here instead of inventing a new per-skill golden requirement.
    """
    path = root / "evals" / "adversarial" / "cases.yaml"
    if not path.is_file():
        return {}
    raw = load_unique_yaml_file(path)
    refs: dict[str, str] = {}
    if not isinstance(raw, dict):
        return refs
    cases = raw.get("cases")
    if not isinstance(cases, list):
        return refs
    for case in cases:
        if not isinstance(case, dict):
            continue
        skill = case.get("skill")
        golden_ref = case.get("golden_ref")
        if isinstance(skill, str) and isinstance(golden_ref, str) and "/" in golden_ref:
            ref_skill, _, ref_case_id = golden_ref.partition("/")
            if ref_skill == skill:
                refs[skill] = ref_case_id
    return refs


def build_per_skill_golden_coverage(root: Path = ROOT) -> dict[str, Any]:
    """Per-skill Tier-3 golden coverage beyond the mandatory adversarial anchor.

    docs/skill-framework/shared/eval-contract.md requires five behavioral
    dimensions per registered skill: positive, negative, ambiguous, adversarial,
    degraded. Of those, only `adversarial` is wired today to a *golden* fixture
    requirement -- see `_adversarial_golden_case_ids` above. `is_healthy()`'s
    Tier-3 check only requires more than zero golden cases *anywhere in the
    repo*, so a skill whose only golden fixture is that one mandatory
    adversarial anchor -- i.e. it has no recorded-output coverage at all for
    its own positive-path, negative, ambiguous, or degraded behavior -- is
    invisible to that check as long as some other skill has Tier-3 coverage.

    This does not invent a new required-case-count threshold: it reuses the
    one per-skill golden requirement the contract already defines (the
    adversarial anchor) and reports, per skill, whether anything beyond it
    exists. A skill flagged here has real Tier-3 golden coverage for its
    prompt-injection guardrail only -- never for the behavior a user actually
    invoked it for.
    """
    registry = parse_registry(root / "skills.yaml")
    golden_cases: list[GoldenCase] = load_golden_fixtures(root / "evals" / "golden")
    case_ids_by_skill: dict[str, list[str]] = {}
    for case in golden_cases:
        case_ids_by_skill.setdefault(case.skill, []).append(case.case_id)
    adversarial_anchor_by_skill = _adversarial_golden_case_ids(root)

    skills_report: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for skill_id in sorted(registry.skills):
        case_ids = case_ids_by_skill.get(skill_id, [])
        anchor = adversarial_anchor_by_skill.get(skill_id)
        non_anchor_case_ids = sorted(case_id for case_id in case_ids if case_id != anchor)
        has_non_adversarial_golden = bool(non_anchor_case_ids)
        skills_report[skill_id] = {
            "golden_case_count": len(case_ids),
            "has_adversarial_anchor": anchor is not None and anchor in case_ids,
            "has_non_adversarial_golden": has_non_adversarial_golden,
        }
        if not has_non_adversarial_golden:
            missing.append(skill_id)

    return {
        "skills": skills_report,
        "skills_missing_non_adversarial_golden": missing,
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
    lines = [
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
    per_skill = report.get("per_skill_golden_coverage")
    if isinstance(per_skill, dict):
        missing = per_skill.get("skills_missing_non_adversarial_golden", [])
        lines.append("### Per-skill Tier-3 golden coverage (WARNING, non-blocking)")
        lines.append("")
        lines.append(
            "Skills below have a Tier-3 golden fixture only for their mandatory "
            "adversarial anchor (evals/adversarial/cases.yaml's `golden_ref`) -- "
            "no golden coverage exists for the behavior the skill is actually "
            "invoked to perform. This does not fail `make lint-static`; it is a "
            "coverage gap for the content-authoring track to close.",
        )
        lines.append("")
        if missing:
            lines.append(f"- Skills missing non-adversarial golden coverage: **{len(missing)}**")
            for skill_id in missing:
                lines.append(f"  - `{skill_id}`")
        else:
            lines.append("- Skills missing non-adversarial golden coverage: **0**")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="markdown")
    args = parser.parse_args()
    report = build_eval_tier_health()
    print(render_markdown(report) if args.format == "markdown" else json.dumps(report, sort_keys=True, indent=2))
    return 0 if is_healthy(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())