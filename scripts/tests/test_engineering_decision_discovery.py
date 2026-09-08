"""RED baseline for the engineering-decision-discovery skill (Child Plan B, Task 1).

None of the routing, skill package, registry/artifact contract, or eval
admission this module exercises exists yet -- Tasks 2-4 of
docs/superpowers/plans/2026-09-05-engineering-decision-discovery-bridge.md
build them. Every test in this module is expected to fail until then; the
exact failure messages recorded at this commit live in
docs/superpowers/specs/2026-09-05-engineering-decision-discovery-red-baseline.md.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evals.__main__ import admit_case, run_all
from scripts.evals.dispatcher import dispatch_prompt
from scripts.evals.transcript import TranscriptCase, TranscriptEvent, run_transcript_case
from scripts.registry.load import load_registry

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


@pytest.mark.parametrize(
    "prompt",
    [
        "Grill me on this architecture decision.",
        "Challenge my plan and question my assumptions.",
        "Stress-test this engineering decision.",
        "What decisions are missing before we implement this design?",
        "Help me decide between these module designs.",
    ],
)
def test_decision_discovery_has_a_dedicated_owner(prompt: str) -> None:
    result = _dispatch(prompt)
    assert result.status == "selected", result
    assert result.owner == "engineering-decision-discovery"


def test_decision_discovery_skill_is_not_yet_registered() -> None:
    """Documents the RED reason every other test in this module fails on: there is
    no `engineering-decision-discovery` entry in skills.yaml yet (Task 3 adds it)."""
    registry = load_registry(ROOT)
    assert "engineering-decision-discovery" in registry.skills


def test_decision_frontier_transcript_fixture_is_admitted_and_passes() -> None:
    """evals/transcripts/engineering-decision-discovery/decision-frontier.yaml requires:
    repository is read before the frontier is computed; a recommendation is recorded
    separately from -- and initially unapproved by -- the human; a human decision
    resolves D1 before D2/D3 enter the frontier; and the repository and an ADR are
    never written. The fixture's events/assertions are already self-consistent, so
    the only reason this currently fails is admission: the skill it names is not yet
    registered (scripts/evals/__main__.py's admit_case gates every case on
    `case.skill in registry.skills`)."""
    results = run_all(ROOT, skill_filter="engineering-decision-discovery")
    by_case_id = {result.case_id: result for result in results}
    assert "decision-frontier" in by_case_id, by_case_id
    result = by_case_id["decision-frontier"]
    assert result.passed, result.messages


def test_decision_record_golden_fixture_is_admitted_and_passes() -> None:
    """evals/golden/engineering-decision-discovery/decision-record.yaml requires the
    typed engineering_decision_record to keep repository/ADR writes at "none", never
    synthesize a human decision, and hold D2/D3 behind the frontier until D1 is
    resolved. Same RED reason as the transcript case above: admission, not the
    recorded content, fails until the skill is registered."""
    results = run_all(ROOT, skill_filter="engineering-decision-discovery")
    by_case_id = {result.case_id: result for result in results}
    assert "decision-record" in by_case_id, by_case_id
    result = by_case_id["decision-record"]
    assert result.passed, result.messages


def test_unattended_execution_blocks_on_unresolved_frontier() -> None:
    """An unattended composition run must not synthesize a human decision to clear a
    material, prerequisite-dependent decision -- it returns BLOCKED with the frontier
    left explicit instead. Modeled here as an in-memory transcript case (rather than a
    committed fixture file) because Task 4 is what formally admits
    evals/transcripts/engineering-decision-discovery/unattended-block.yaml into the
    eval suite; this test exercises the same admit_case/run_transcript_case path
    Task 4's fixture will use, so it already proves the RED reason (skill not
    registered) without pre-empting that later file."""
    case = TranscriptCase(
        skill="engineering-decision-discovery",
        case_id="unattended-block",
        tier=2,
        description=(
            "Unattended execution blocks on an unresolved, prerequisite-dependent "
            "decision instead of synthesizing a human decision for it."
        ),
        events=[
            TranscriptEvent("tool", {"name": "repository_read"}),
            TranscriptEvent("decision_frontier", {"decisions": ["D1"]}),
            TranscriptEvent("outcome", {"status": "BLOCKED"}),
        ],
        assertions=[
            {"type": "tool_not_called", "name": "repository_write"},
            {"type": "tool_not_called", "name": "write_adr"},
            {"type": "outcome_status", "status": "BLOCKED"},
        ],
        path=ROOT / "evals" / "transcripts" / "engineering-decision-discovery" / "unattended-block.yaml",
    )
    # No human_decision event is present at all -- BLOCKED must not depend on one
    # being synthesized to reach that outcome.
    assert not any(event.event_type == "human_decision" for event in case.events)

    registry = load_registry(ROOT)
    result = admit_case(case, run_transcript_case, seen=set(), registry=registry)
    assert result.passed, result.messages
