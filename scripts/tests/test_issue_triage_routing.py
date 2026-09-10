"""Routing regression coverage for issue-triage."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


def test_triage_raw_issues_routes_to_issue_triage() -> None:
    result = _dispatch("Triage these incoming bug reports and tell me which are duplicates.")
    assert result.status == "selected", result
    assert result.owner == "issue-triage"


def test_overnight_tracker_sweep_does_not_route_to_issue_triage() -> None:
    """Mirrors evals/negative/cases.yaml's issue-triage row.

    Asserted against `.candidates`, not `.owner`: `DispatchResult.owner` is None for any
    non-`selected` result, so `owner != "issue-triage"` would pass vacuously if a future
    pattern change made issue-triage a false *candidate* here (status goes `ambiguous`
    alongside backlog-runner) rather than the sole, wrongly `selected` owner -- the exact
    regression class this test exists to catch. See research-brief's own routing test
    (branch `research-brief-skill`) for the identical fix, applied there after its round-2
    review found this same vacuous-assertion shape.
    """
    result = _dispatch("Run backlog tickets overnight and implement each one until zero issues.")
    assert "issue-triage" not in result.candidates, result


def test_paging_webhook_does_not_route_to_issue_triage() -> None:
    """Same `.owner`-vs-`.candidates` characteristic as the test above: asserted against
    `.candidates` so it still catches issue-triage becoming a false candidate alongside
    incident-triage-agent (status `ambiguous`), not just a wrongly `selected` sole owner.
    """
    result = _dispatch("Handle the pager alert webhook and triage the incident.")
    assert "issue-triage" not in result.candidates, result


def _positive_cases() -> list[tuple[str, str]]:
    raw = load_unique_yaml_file(ROOT / "evals" / "positive" / "cases.yaml")
    assert isinstance(raw, dict)
    return [
        (case["skill"], case["prompt"])
        for case in raw["cases"]
        if case["skill"] != "issue-triage"
    ]


def _wrapped_duplicate(prompt: str) -> list[str]:
    lowered = prompt[0].lower() + prompt[1:] if prompt else prompt
    lowered = lowered.rstrip(".?")
    return [
        f"Is this a duplicate? {lowered}.",
        f"{prompt} Is this a duplicate of something else?",
    ]


# Two known, accepted residual false positives: a compound sentence where "duplicate" and an
# unrelated later "issues"/"tickets" word (from loop-task-implementer's or backlog-runner's own
# vocabulary) both appear, satisfying the anchored pattern's unbounded co-occurrence even though
# the sentence has nothing to do with issue duplication. This is the same "unbounded .*, no
# proximity bound" characteristic every other pattern in this registry already has -- accepted as
# a documented, reduced-not-eliminated residual (see research-brief's PR for the identical
# precedent), not chased further with proximity-bounded regex this registry has never used.
#
# - ("loop-task-implementer", 0): "Is this a duplicate? implement this task, review the changes,
#   fix issues, and repeat until zero issues." -- pattern 3 (anchor after "a duplicate") fires on
#   "fix issues" appearing later in the same sentence.
# - ("loop-task-implementer", 1): "Implement this task, review the changes, fix issues, and
#   repeat until zero issues. Is this a duplicate of something else?" -- pattern 4 (anchor before
#   "is this") fires on "zero issues" appearing earlier in the same sentence.
# - ("backlog-runner", 0): "Is this a duplicate? run the backlog tickets overnight with the
#   scheduled queue runner." -- pattern 3 fires on "tickets" appearing later in the sentence.
# - ("backlog-runner", 1): "Run the backlog tickets overnight with the scheduled queue runner. Is
#   this a duplicate of something else?" -- pattern 4 fires on "tickets" appearing earlier in the
#   sentence.
KNOWN_DUPLICATE_PATTERN_OVERLAPS = {
    ("loop-task-implementer", 0): True,
    ("loop-task-implementer", 1): True,
    ("backlog-runner", 0): True,
    ("backlog-runner", 1): True,
}


@pytest.mark.parametrize(
    ("skill", "prompt", "wrapper_idx"),
    [
        pytest.param(skill, wrapped, idx, id=f"{skill}-dup-wrapper-{idx}")
        for skill, base_prompt in _positive_cases()
        for idx, wrapped in enumerate(_wrapped_duplicate(base_prompt))
    ],
)
def test_issue_triage_duplicate_pattern_does_not_capture_other_skills(skill: str, prompt: str, wrapper_idx: int) -> None:
    """Registry-wide guard against issue-triage's anchored "is this a duplicate" pattern
    still going topic-free for some other skill's own trigger phrase.

    The plan's original bare `\\bis this\\b.*\\ba duplicate\\b` pattern (replaced in Task 2) failed
    118 of 172 combinations of this exact sweep. The anchored replacement (requiring co-occurrence
    with issue/bug/ticket/report vocabulary, in 3 word orderings) brings that down to a small,
    documented residual -- see KNOWN_DUPLICATE_PATTERN_OVERLAPS above for the exact accepted cases.
    """
    result = _dispatch(prompt)
    if "issue-triage" in result.candidates:
        # Only acceptable if this exact (skill, wrapper_idx) is a documented, accepted residual.
        assert KNOWN_DUPLICATE_PATTERN_OVERLAPS.get((skill, wrapper_idx)), (skill, prompt, result)
