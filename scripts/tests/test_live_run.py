"""Tests for the live-run CLI wiring — injects ScriptedModelClient, never hits the network."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.evals.live_run import ROOT, build_system_prompt, load_live_case, run_from_case, score_against_golden, write_transcript
from scripts.tests.live_test_helpers import ScriptedModelClient, ScriptedTurn

EXAMPLE_LIVE_CASE = ROOT / "evals" / "live" / "squad-map" / "single-repo-clean-map.yaml"


def _write_skill(repo_root: Path, skill: str, skill_md: str) -> None:
    skill_dir = repo_root / skill
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(skill_md, encoding="utf-8")


def _write_live_case(path: Path, **overrides: object) -> Path:
    case = {
        "schema_version": 1,
        "skill": "demo-skill",
        "case_id": "demo-case",
        "description": "demo",
        "scenario_prompt": "map the one repo in scope",
        "tool_defs": [
            {"name": "lookup", "description": "d", "input_schema": {"type": "object", "properties": {}}},
        ],
        "mock_tools": {"lookup": {"squad": "payments"}},
        "max_turns": 5,
    }
    case.update(overrides)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(case, sort_keys=False), encoding="utf-8")
    return path


def test_build_system_prompt_appends_harness_note(tmp_path: Path) -> None:
    _write_skill(tmp_path, "demo-skill", "# Demo Skill\n\ndo the thing\n")
    prompt = build_system_prompt(tmp_path, "demo-skill", "")
    assert prompt.startswith("# Demo Skill")
    assert "record_outcome" in prompt
    assert "mock-tool evaluation harness" in prompt


def test_build_system_prompt_missing_skill_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no SKILL.md"):
        build_system_prompt(tmp_path, "no-such-skill", "")


def test_run_from_case_drives_harness_with_injected_client(tmp_path: Path) -> None:
    _write_skill(tmp_path, "demo-skill", "# Demo Skill\n")
    case_path = _write_live_case(tmp_path / "case.yaml")

    client = ScriptedModelClient(
        [
            ScriptedTurn(tool_calls=[("lookup", {})]),
            ScriptedTurn(tool_calls=[("record_outcome", {"status": "completed", "output": {"squad": "payments"}})]),
        ],
    )

    case, result = run_from_case(case_path, client=client, repo_root=tmp_path)

    assert case["skill"] == "demo-skill"
    assert result.recorded_output == {"squad": "payments", "status": "completed"}
    assert result.events[0] == {"type": "tool", "name": "lookup", "args": {}}


def test_score_against_golden_reuses_golden_engine(tmp_path: Path) -> None:
    golden_path = tmp_path / "golden.yaml"
    golden_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "skill": "demo-skill",
                "case_id": "demo-case",
                "tier": 3,
                "description": "d",
                "assertions": [{"type": "field_equals", "path": "squad", "value": "payments"}],
            },
        ),
        encoding="utf-8",
    )

    passing = score_against_golden(
        golden_path,
        skill="demo-skill",
        case_id="demo-case",
        recorded_output={"squad": "payments"},
    )
    assert passing.passed

    failing = score_against_golden(
        golden_path,
        skill="demo-skill",
        case_id="demo-case",
        recorded_output={"squad": "checkout"},
    )
    assert not failing.passed
    assert "payments" in failing.messages[0]


def test_write_transcript_bootstraps_new_fixture_from_case_assertions(tmp_path: Path) -> None:
    case = {
        "skill": "demo-skill",
        "case_id": "demo-case",
        "description": "d",
        "transcript_assertions": [{"type": "outcome_status", "status": "completed"}],
    }
    events = [{"type": "tool", "name": "lookup", "args": {}}, {"type": "outcome", "status": "completed"}]
    transcript_path = tmp_path / "evals" / "transcripts" / "demo-skill" / "demo-case.yaml"

    write_transcript(transcript_path, case, events, note="pytest")

    raw = yaml.safe_load(transcript_path.read_text(encoding="utf-8"))
    assert raw["skill"] == "demo-skill"
    assert raw["events"] == events
    assert raw["assertions"] == case["transcript_assertions"]
    assert raw["refresh_meta"]["refresh_note"] == "pytest"

    from scripts.evals.transcript import load_transcript_fixtures, run_transcript_case

    loaded = load_transcript_fixtures(transcript_path.parent.parent)
    assert len(loaded) == 1
    assert run_transcript_case(loaded[0]).passed


def test_write_transcript_refreshes_existing_fixture_events_only(tmp_path: Path) -> None:
    transcript_path = tmp_path / "existing.yaml"
    transcript_path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "skill": "demo-skill",
                "case_id": "demo-case",
                "tier": 2,
                "description": "original description",
                "events": [{"type": "outcome", "status": "stale"}],
                "assertions": [{"type": "outcome_status", "status": "completed"}],
            },
        ),
        encoding="utf-8",
    )

    new_events = [{"type": "outcome", "status": "completed"}]
    write_transcript(transcript_path, {"skill": "demo-skill", "case_id": "demo-case"}, new_events, note="refresh")

    raw = yaml.safe_load(transcript_path.read_text(encoding="utf-8"))
    assert raw["events"] == new_events
    assert raw["description"] == "original description"
    assert raw["assertions"] == [{"type": "outcome_status", "status": "completed"}]


def test_example_live_case_fixture_loads_and_builds_a_real_system_prompt() -> None:
    case = load_live_case(EXAMPLE_LIVE_CASE)
    assert case["skill"] == "squad-map"
    assert case["mock_tools"]  # non-empty
    assert case["tool_defs"]

    prompt = build_system_prompt(ROOT, case["skill"], "")
    assert "Squad Map" in prompt
    assert "record_outcome" in prompt


def test_write_transcript_without_assertions_and_no_existing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="transcript_assertions"):
        write_transcript(
            tmp_path / "new.yaml",
            {"skill": "demo-skill", "case_id": "demo-case"},
            [{"type": "outcome", "status": "completed"}],
            note="pytest",
        )
