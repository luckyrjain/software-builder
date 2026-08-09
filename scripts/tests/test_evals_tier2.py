"""Tests for Tier-2 transcript behavioral evals."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_transcript_fixtures_load() -> None:
    from scripts.evals.transcript import load_transcript_fixtures

    cases = load_transcript_fixtures(ROOT / "evals" / "transcripts")
    case_ids = {(case.skill, case.case_id) for case in cases}
    assert ("pr-gatekeeper", "duplicate-webhook-short-circuit") in case_ids
    assert ("pr-review", "chat-only-no-gitlab-write") in case_ids
    assert ("loop-task-implementer", "builder-ci-not-authoritative") in case_ids


def test_transcript_cases_pass_on_repository() -> None:
    from scripts.evals.__main__ import run_all

    results = run_all(ROOT, tier_filter=2)
    failures = [result for result in results if not result.passed]
    assert failures == [], failures


def test_transcript_tool_not_called_detects_violation(tmp_path: Path) -> None:
    from scripts.evals.transcript import TranscriptCase, TranscriptEvent, run_transcript_case

    case = TranscriptCase(
        skill="demo",
        case_id="bad-post",
        tier=2,
        description="",
        events=[
            TranscriptEvent("tool", {"name": "post_merge_request_comment"}),
            TranscriptEvent("outcome", {"status": "complete"}),
        ],
        assertions=[{"type": "tool_not_called", "name": "post_merge_request_comment"}],
        path=tmp_path / "bad.yaml",
    )
    result = run_transcript_case(case)
    assert not result.passed
    assert "forbidden tool" in result.messages[0]


def test_transcript_forbid_tool_before_gate(tmp_path: Path) -> None:
    from scripts.evals.transcript import TranscriptCase, TranscriptEvent, run_transcript_case

    case = TranscriptCase(
        skill="demo",
        case_id="early-post",
        tier=2,
        description="",
        events=[
            TranscriptEvent("tool", {"name": "post_merge_request_comment"}),
            TranscriptEvent("gate", {"name": "phase_3_confirmation", "decision": "post_all"}),
        ],
        assertions=[
            {
                "type": "forbid_tool_before_gate",
                "tool": "post_merge_request_comment",
                "gate": "phase_3_confirmation",
            },
        ],
        path=tmp_path / "early.yaml",
    )
    result = run_transcript_case(case)
    assert not result.passed


def test_transcript_tool_call_count_requires_bound(tmp_path: Path) -> None:
    from scripts.evals.transcript import TranscriptCase, TranscriptEvent, run_transcript_case

    case = TranscriptCase(
        skill="demo",
        case_id="unbounded-count",
        tier=2,
        description="",
        events=[TranscriptEvent("tool", {"name": "merge_pull_request"})],
        assertions=[{"type": "tool_call_count", "name": "merge_pull_request"}],
        path=tmp_path / "unbounded.yaml",
    )
    result = run_transcript_case(case)
    assert not result.passed
    from scripts.evals.__main__ import run_all

    tier1 = run_all(ROOT, tier_filter=1)
    tier2 = run_all(ROOT, tier_filter=2)
    tier1_ids = {result.case_id for result in tier1}
    tier2_ids = {result.case_id for result in tier2}
    assert len(tier2_ids) == 6
    assert "duplicate-webhook-short-circuit" in tier2_ids
    assert "duplicate-webhook-short-circuit" not in tier1_ids
