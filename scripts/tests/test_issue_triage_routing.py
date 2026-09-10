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

    This row is held by the include patterns alone -- it fires none of them -- which is why
    the `\\bovernight\\b.*\\btracker query\\b` exclude that used to "protect" it was removed as
    dead. Keeping this assertion green with that exclude gone is the proof.
    """
    result = _dispatch("Run backlog tickets overnight and implement each one until zero issues.")
    assert result.owner == "backlog-runner", result
    assert "issue-triage" not in result.candidates, result


def test_overnight_tracker_query_triage_request_still_has_an_owner() -> None:
    """An exclude must never be able to leave a prompt with no owner at all.

    The removed `\\bovernight\\b.*\\btracker query\\b` exclude did exactly that here: this
    prompt fires include patterns 1 and 2, the exclude stripped issue-triage, and
    backlog-runner's own pattern then failed to pick it up because that pattern requires
    "tickets" BEFORE "overnight" and this phrasing puts it after -- so the request went
    no_match and no skill was responsible for it. no_match is the one dispatcher outcome
    with no recovery path; `ambiguous` at least reaches a human.
    """
    result = _dispatch("Triage the overnight tracker query results and classify these tickets.")
    assert result.status != "no_match", result
    assert "issue-triage" in result.candidates, result


def test_incidental_pr_mention_does_not_strip_an_in_domain_triage_request() -> None:
    """The PR/MR excludes must fire on a review request, not on a passing PR reference.

    Their bare, contextless original form cost every one of these prompts its owner; the
    narrowed review/merge/approve co-occurrence form leaves all of them with issue-triage
    while still handing a genuine review request to pr-review.
    """
    for prompt in (
        "Triage these incoming bug reports: one references PR #456 as a related fix.",
        "Triage these incoming tickets and note which ones a merge request already closed.",
        "Classify these issues by severity — issue 3 says the bug appeared right after PR !88 shipped.",
    ):
        result = _dispatch(prompt)
        assert result.owner == "issue-triage", (prompt, result)

    review_request = _dispatch("Triage these issues: please review and merge this PR that fixes one of them.")
    assert "issue-triage" not in review_request.candidates, review_request


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
        # Wrapper styles 2-5 put the anchor noun INSIDE the wrapper phrase itself, which is the
        # slot a real wrapper-writer would naturally use ("is this ticket a duplicate?"). Round
        # 1's anchored-but-bare `\ba duplicate\b` pattern was topic-free under exactly these and
        # nothing exercised them, so the collision (41 of 43 siblings under style 2 alone) went
        # undetected for a whole review round. Keep one template per wrapper style: a pattern
        # that no template exercises is a pattern nothing has verified.
        f"Is this issue a duplicate? {lowered}.",
        f"Is this ticket a duplicate? {lowered}.",
        f"Is this bug a duplicate? {lowered}.",
        f"Is this report a duplicate? {lowered}.",
    ]


# Two known, accepted residual false positives, both under wrapper style 1: a compound sentence
# where the wrapper's own trailing literal "a duplicate of" and an unrelated EARLIER
# "issues"/"tickets" word (from loop-task-implementer's or backlog-runner's own vocabulary) both
# appear, satisfying pattern 4's unbounded co-occurrence even though the sentence has nothing to
# do with issue duplication. This is the same "unbounded .*, no proximity bound" characteristic
# every other pattern in this registry already has -- accepted as a documented,
# reduced-not-eliminated residual (see research-brief's PR for the identical precedent), not
# chased further with proximity-bounded regex this registry has never used.
#
# - ("loop-task-implementer", 1): "Implement this task, review the changes, fix issues, and
#   repeat until zero issues. Is this a duplicate of something else?" -- pattern 4 (anchor before
#   "is this") fires on "zero issues" appearing earlier in the sentence.
# - ("backlog-runner", 1): "Run the backlog tickets overnight with the scheduled queue runner. Is
#   this a duplicate of something else?" -- pattern 4 fires on "tickets" appearing earlier in the
#   sentence.
#
# The two wrapper-style-0 entries this map used to carry (same two skills) are GONE, not
# forgotten: style 0 is "Is this a duplicate? {sibling text}", where "duplicate" is followed by
# "?" rather than the literal "of", so the restructured `\ba duplicate of\b` patterns no longer
# reach it at all. The 4 anchor-inside-the-wrapper styles (2-5) likewise contribute zero
# overlaps, for the same reason. Measured: 256 of 258 combinations clean.
#
# This map is an allowlist, so a stale entry is invisible by construction -- it would silently
# keep passing a collision that no longer exists, and mask the day it comes back for a different
# reason. test_known_duplicate_pattern_overlaps_are_not_stale below fails if any entry stops
# overlapping, which is how the two dead style-0 entries were caught.
KNOWN_DUPLICATE_PATTERN_OVERLAPS = {
    ("loop-task-implementer", 1): True,
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
    """Registry-wide guard against issue-triage's duplicate pattern still going topic-free for
    some other skill's own trigger phrase.

    The plan's original bare `\\bis this\\b.*\\ba duplicate\\b` pattern failed 118 of 172
    combinations of this sweep. Round 1's anchored-but-still-bare replacement passed that sweep
    but failed 41 of 43 siblings under the "Is this issue a duplicate? {sibling text}" wrapper,
    which the sweep did not yet exercise -- the anchor noun sat inside the wrapper phrase itself.
    Requiring the adjacent phrase `\\ba duplicate of\\b` closes that class structurally: 256 of
    258 combinations clean, residuals in KNOWN_DUPLICATE_PATTERN_OVERLAPS above.
    """
    result = _dispatch(prompt)
    if "issue-triage" in result.candidates:
        # Only acceptable if this exact (skill, wrapper_idx) is a documented, accepted residual.
        assert KNOWN_DUPLICATE_PATTERN_OVERLAPS.get((skill, wrapper_idx)), (skill, prompt, result)


def test_known_duplicate_pattern_overlaps_are_not_stale() -> None:
    """Every allowlisted residual must still actually overlap.

    Without this, KNOWN_DUPLICATE_PATTERN_OVERLAPS rots one direction only: entries whose
    collision a later pattern fix removed keep sitting there, documenting a defect that no longer
    exists and pre-authorizing its return. Two such entries were already found dead this way.
    """
    by_skill = dict(_positive_cases())
    for skill, wrapper_idx in KNOWN_DUPLICATE_PATTERN_OVERLAPS:
        assert skill in by_skill, f"allowlisted skill {skill!r} is no longer in evals/positive/cases.yaml"
        prompt = _wrapped_duplicate(by_skill[skill])[wrapper_idx]
        result = _dispatch(prompt)
        assert "issue-triage" in result.candidates, (
            f"stale allowlist entry {(skill, wrapper_idx)!r}: no longer overlaps, remove it "
            f"(prompt={prompt!r}, result={result!r})"
        )
