#!/usr/bin/env python3
"""Run a skill live against a real model, tools mocked from a fixture, and optionally score/record.

This is the CLI over `live_harness.py` (see that module's docstring for the mechanism). Deliberately
outside `make lint`/CI — needs `ANTHROPIC_API_KEY`, costs real tokens, and is not turn-for-turn
reproducible, all of which conflict with the deterministic CI `make lint` depends on (ADR 0004,
docs/evals/LIVE-HARNESS.md). Run it by hand, or from a maintainer-triggered, non-required workflow
(`.github/workflows/live-eval.yml`, `workflow_dispatch` only).

Usage:
  # Score a live run against an existing Tier-3 golden fixture's assertions ("live model scoring"):
  python3 -m scripts.evals.live_run --live-case evals/live/squad-map/single-repo-clean-map.yaml \\
    --score-golden evals/golden/squad-map/some-case.yaml

  # Refresh a Tier-2 transcript fixture's events from a real run:
  python3 -m scripts.evals.live_run --live-case evals/live/squad-map/single-repo-clean-map.yaml \\
    --write-transcript evals/transcripts/squad-map/single-repo-clean-map.yaml

  # Just capture recorded_output for scripts/evals/golden_refresh.py's existing flow:
  python3 -m scripts.evals.live_run --live-case evals/live/squad-map/single-repo-clean-map.yaml \\
    --recorded-output-out /tmp/out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from scripts.evals.golden import GoldenCase, run_golden_case
from scripts.evals.live_harness import (
    AnthropicModelClient,
    LiveHarnessError,
    LiveRunResult,
    ModelClient,
    load_mock_tools,
    run_live_case,
)
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL = "claude-sonnet-5"

_REQUIRED_LIVE_CASE_KEYS = ("skill", "case_id", "scenario_prompt", "mock_tools")


def load_live_case(path: Path) -> dict[str, Any]:
    raw = load_unique_yaml_file(path)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: live case root must be a mapping")
    missing = [key for key in _REQUIRED_LIVE_CASE_KEYS if key not in raw]
    if missing:
        raise ValueError(f"{path}: missing required key(s): {missing}")
    return raw


def build_system_prompt(repo_root: Path, skill: str, extra: str) -> str:
    skill_md_path = repo_root / skill / "SKILL.md"
    if not skill_md_path.is_file():
        raise ValueError(f"no SKILL.md for skill {skill!r} under {repo_root}")
    skill_md = skill_md_path.read_text(encoding="utf-8")
    harness_note = (
        "\n\n---\nHarness note: you are running inside a mock-tool evaluation harness. Every tool call "
        "you make is answered from a fixture, never a live system. When this skill's instructions call "
        "for an explicit policy gate decision, call record_gate_decision(name, decision, reason). When "
        "you are done, call record_outcome(status, output) exactly once with the skill's final "
        "structured result as `output` — never just describe the result in prose."
    )
    return skill_md + harness_note + (f"\n\n{extra}" if extra else "")


def run_from_case(
    case_path: Path,
    *,
    model: str = DEFAULT_MODEL,
    api_key: str | None = None,
    client: ModelClient | None = None,
    repo_root: Path = ROOT,
) -> tuple[dict[str, Any], LiveRunResult]:
    case = load_live_case(case_path)
    tool_defs = case.get("tool_defs", [])
    if not isinstance(tool_defs, list):
        raise ValueError(f"{case_path}: tool_defs must be a list")
    mock_tools_raw = case["mock_tools"]
    if not isinstance(mock_tools_raw, dict):
        raise ValueError(f"{case_path}: mock_tools must be a mapping")

    system_prompt = build_system_prompt(repo_root, str(case["skill"]), str(case.get("system_prompt_extra", "")))
    active_client = client or AnthropicModelClient(model=model, api_key=api_key)
    result = run_live_case(
        system_prompt=system_prompt,
        scenario_prompt=str(case["scenario_prompt"]),
        tool_defs=tool_defs,
        mock_tools=load_mock_tools(mock_tools_raw),
        client=active_client,
        max_turns=int(case.get("max_turns", 12)),
    )
    return case, result


def score_against_golden(
    golden_path: Path,
    *,
    skill: str,
    case_id: str,
    recorded_output: dict[str, Any],
):
    raw = load_unique_yaml_file(golden_path)
    if not isinstance(raw, dict):
        raise ValueError(f"{golden_path}: golden fixture root must be a mapping")
    assertions = raw.get("assertions", [])
    if not isinstance(assertions, list) or not assertions:
        raise ValueError(f"{golden_path}: assertions must be a non-empty list")
    case = GoldenCase(
        skill=skill,
        case_id=case_id,
        tier=int(raw.get("tier", 3)),
        description=str(raw.get("description", "")),
        recorded_output=recorded_output,
        assertions=assertions,
        path=golden_path,
    )
    return run_golden_case(case)


def write_transcript(
    transcript_path: Path,
    case: dict[str, Any],
    events: list[dict[str, Any]],
    note: str,
) -> None:
    if transcript_path.is_file():
        raw = load_unique_yaml_file(transcript_path)
        if not isinstance(raw, dict):
            raise ValueError(f"{transcript_path}: root must be a mapping")
        # Refuse to refresh a file that isn't actually the Tier-2 fixture for this case: neither
        # a mapping missing the fields Tier-2's own loader requires, nor — the more dangerous
        # case — a real, valid fixture that just belongs to a different skill/case_id (a
        # copy-paste or typo'd --write-transcript path). Either would silently either produce an
        # invalid fixture or overwrite an unrelated one's events while it keeps the old
        # skill/case_id label and assertions never written for the new events.
        assertions = raw.get("assertions")
        if not isinstance(assertions, list) or not assertions:
            raise ValueError(
                f"{transcript_path}: not a valid Tier-2 fixture (missing a non-empty 'assertions' "
                "list) — refusing to overwrite; point --write-transcript at a real existing fixture "
                "or a path that doesn't exist yet",
            )
        if raw.get("skill") != case["skill"] or raw.get("case_id") != case["case_id"]:
            raise ValueError(
                f"{transcript_path}: belongs to skill={raw.get('skill')!r}/case_id={raw.get('case_id')!r}, "
                f"but this live run is skill={case['skill']!r}/case_id={case['case_id']!r} — refusing to "
                "overwrite a fixture that doesn't match this case",
            )
    else:
        bootstrap_assertions = case.get("transcript_assertions")
        if not bootstrap_assertions:
            raise ValueError(
                f"{transcript_path} does not exist yet and the live case has no transcript_assertions to "
                "bootstrap one — add transcript_assertions to the live case, or point --write-transcript "
                "at an existing Tier-2 fixture to refresh instead",
            )
        raw = {
            "schema_version": 1,
            "skill": case["skill"],
            "case_id": case["case_id"],
            "tier": 2,
            "description": str(case.get("description", "")),
            "assertions": bootstrap_assertions,
        }

    raw["events"] = events
    refresh_meta = raw.setdefault("refresh_meta", {})
    if not isinstance(refresh_meta, dict):
        raise ValueError(f"{transcript_path}: refresh_meta must be a mapping")
    refresh_meta["last_refreshed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    refresh_meta["refresh_note"] = note

    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(yaml.safe_dump(raw, sort_keys=False, allow_unicode=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--live-case", required=True, type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--api-key", default=None, help="defaults to ANTHROPIC_API_KEY")
    parser.add_argument(
        "--score-golden",
        type=Path,
        help="score the live run's recorded_output against this Tier-3 golden fixture's assertions",
    )
    parser.add_argument(
        "--write-transcript",
        type=Path,
        help="write/refresh this Tier-2 transcript fixture's events from the live run",
    )
    parser.add_argument(
        "--recorded-output-out",
        type=Path,
        help="write the raw recorded_output JSON here (feed to scripts.evals.golden_refresh)",
    )
    parser.add_argument("--note", default="live model run via scripts.evals.live_run")
    args = parser.parse_args(argv)

    try:
        case, result = run_from_case(args.live_case.resolve(), model=args.model, api_key=args.api_key)
    except (LiveHarnessError, ValueError, OSError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"ok: {case['skill']}/{case['case_id']} — {result.turns_used} turn(s), {len(result.events)} event(s)")

    if args.recorded_output_out:
        try:
            args.recorded_output_out.write_text(
                json.dumps(result.recorded_output, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {args.recorded_output_out}")

    if args.write_transcript:
        try:
            write_transcript(args.write_transcript.resolve(), case, result.events, args.note)
        except (ValueError, OSError, yaml.YAMLError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"wrote {args.write_transcript}")

    exit_code = 0
    if args.score_golden:
        try:
            eval_result = score_against_golden(
                args.score_golden.resolve(),
                skill=str(case["skill"]),
                case_id=str(case["case_id"]),
                recorded_output=result.recorded_output,
            )
        except (ValueError, OSError, yaml.YAMLError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if not eval_result.passed:
            print(f"FAIL: live model output did not match {args.score_golden}'s assertions:", file=sys.stderr)
            for message in eval_result.messages:
                print(f"  - {message}", file=sys.stderr)
            exit_code = 1
        else:
            print(f"ok: live model output matched all assertions in {args.score_golden}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
