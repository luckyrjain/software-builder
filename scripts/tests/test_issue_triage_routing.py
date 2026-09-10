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

    These excludes now MIRROR pr-review's own two include patterns verbatim, which is what
    makes orphaning impossible by construction: the exclude fires if and only if pr-review's
    own include also fires, so a stripped prompt always lands with pr-review. The previous
    `merge (it|this)`/`approve` form used vocabulary pr-review does NOT recognise, so it
    stripped issue-triage from prompts pr-review then declined to pick up. Verified on the
    live dispatcher: the last four prompts below were all `no_match` before this change.
    """
    for prompt in (
        "Triage these incoming bug reports: one references PR #456 as a related fix.",
        "Triage these incoming tickets and note which ones a merge request already closed.",
        "Classify these issues by severity — issue 3 says the bug appeared right after PR !88 shipped.",
        "Triage these incoming tickets: one asks us to approve the vendor merge request before the sprint ends.",
        "Classify these bugs — the reporter says a pull request fixed it, just approve it and close the ticket.",
        "Triage these raw issues: the last one just says merge this pull request already.",
        "Classify these incoming bug reports; one wants us to approve the MR that reverts the change.",
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


def test_incidental_webhook_mention_does_not_strip_an_in_domain_triage_request() -> None:
    """The pager exclude's own orphaning bug, the mirror-image of the PR/MR one above.

    Its previous form, `\\b(pager|page-fire|webhook)\\b.*\\bincident\\b`, fired on a bare
    "webhook" and on "page-fire" -- neither of which appears in incident-triage-agent's own
    patterns -- and keyed on "incident" where that skill keys on triage/automation/route/owner.
    Both prompts below were therefore `no_match` before this change: stripped from issue-triage
    and picked up by nobody. Mirroring incident-triage-agent's own two patterns makes that
    impossible, because the exclude can no longer fire where its include does not.
    """
    for prompt in (
        "Classify these issues — the reporter mentions a webhook that fired during the incident.",
        "Classify these bugs about the alert webhook that duplicated an incident notification.",
    ):
        result = _dispatch(prompt)
        assert result.owner == "issue-triage", (prompt, result)


def test_bare_duplicate_question_no_longer_routes_anywhere() -> None:
    """The accepted recall loss, pinned so it is a decision rather than a drift.

    A standalone duplicate question with no "triage"/"classify" word is deliberately NOT this
    skill's trigger any more: the construction is domain-neutral English, so every attempt to
    make it safe on its own (bare, then anchored, then adjacency-bound) falsely captured other
    skills' requests instead. If a future edit makes any of these match again, that edit has
    reopened the collision surface -- see the routing comment in
    scripts/registry/skills.d/issue-triage.yaml for why no noun set can close it.
    """
    for prompt in (
        "Is this a duplicate of the CVE we already patched last month?",
        "Is this a duplicate migration script from last sprint?",
        "Is this a duplicate PR of the one already merged?",
        "Is this a duplicate finding in the security scan?",
        "Is this a duplicate deployment config?",
        "Is this a duplicate of the CVE ticket we already tracked?",
        "Isn't this the same bug we already fixed in the payment service?",
    ):
        result = _dispatch(prompt)
        assert "issue-triage" not in result.candidates, (prompt, result)


def test_triage_framed_duplicate_questions_still_route_here() -> None:
    """...and the recall that the co-occurrence requirement keeps: framed as triage, it routes."""
    for prompt in (
        "Triage this: is this a duplicate of issue #42?",
        "Classify this bug report — is this a duplicate of one already filed?",
        "Classify this incoming ticket — is this a duplicate, same repro steps as the one filed last week?",
        "Triage these raw feature requests.",
        "Classify these incoming tickets by category.",
    ):
        result = _dispatch(prompt)
        assert result.status == "selected", (prompt, result)
        assert result.owner == "issue-triage", (prompt, result)


def _positive_cases() -> list[tuple[str, str]]:
    raw = load_unique_yaml_file(ROOT / "evals" / "positive" / "cases.yaml")
    assert isinstance(raw, dict)
    return [
        (case["skill"], case["prompt"])
        for case in raw["cases"]
        if case["skill"] != "issue-triage"
    ]


def _wrapped_duplicate(prompt: str) -> list[str]:
    """One template per wrapper STYLE, and the styles are the point.

    Rounds 1 and 2 each shipped a hole that this sweep was green on, purely because the sweep
    had no template for the style that broke it: round 1 for the anchor-inside-the-wrapper
    styles ("Is this issue a duplicate? {sibling text}"), round 2 for the same trick one word
    later ("Is this a duplicate of an existing issue? {sibling text}"). A wrapper style no
    template exercises is a style nothing has verified, so this list is now deliberately
    exhaustive over the shapes a wrapper-writer can reach for -- anchor before "a duplicate",
    anchor after "of", anchor as a compound noun, and the negated/perfect paraphrases that mean
    the same thing without the word "duplicate" in the same slot. Add to it, never trim it.
    """
    lowered = prompt[0].lower() + prompt[1:] if prompt else prompt
    lowered = lowered.rstrip(".?")
    return [
        # 0-1: the original bare wrapper, leading and trailing.
        f"Is this a duplicate? {lowered}.",
        f"{prompt} Is this a duplicate of something else?",
        # 2-5: anchor noun INSIDE the wrapper phrase, before "a duplicate" -- the slot that broke
        # round 1's anchored patterns (41 of 43 siblings collided under style 2 alone).
        f"Is this issue a duplicate? {lowered}.",
        f"Is this ticket a duplicate? {lowered}.",
        f"Is this bug a duplicate? {lowered}.",
        f"Is this report a duplicate? {lowered}.",
        # 6-8: anchor noun after "of", or as a compound noun -- the slot that broke round 2's
        # `\ba duplicate of\b` adjacency fix (287 of 301 combinations collided).
        f"Is this a duplicate of an existing issue? {lowered}.",
        f"Is this a duplicate of an existing ticket? {lowered}.",
        f"Is this a duplicate bug report? {lowered}.",
        # 9-11: paraphrases that carry the same intent without the literal "a duplicate" in the
        # same position, so a future pattern cannot pass this sweep by keying on surface form.
        f"Isn't this the same as an existing issue? {lowered}.",
        f"Hasn't this already been reported as a bug? {lowered}.",
        f"Wasn't this a duplicate ticket? {lowered}.",
    ]


@pytest.mark.parametrize(
    ("skill", "prompt", "wrapper_idx"),
    [
        pytest.param(skill, wrapped, idx, id=f"{skill}-dup-wrapper-{idx}")
        for skill, base_prompt in _positive_cases()
        for idx, wrapped in enumerate(_wrapped_duplicate(base_prompt))
    ],
)
def test_issue_triage_duplicate_pattern_does_not_capture_other_skills(skill: str, prompt: str, wrapper_idx: int) -> None:
    """Registry-wide guard against issue-triage's duplicate patterns going topic-free for some
    other skill's own trigger phrase.

    History, because the shape of the fix only makes sense against it: the plan's original bare
    `\bis this\b.*\ba duplicate\b` failed 118 of 172 combinations. Round 1 required a
    co-occurring issue/bug/ticket/report ANCHOR and failed 41 of 43 siblings once the anchor was
    placed inside the wrapper. Round 2 required the adjacent literal `\ba duplicate of\b` and
    failed 287 of 301 once the anchor moved just past "of". The generalisation is that a regex
    with no proximity or lookahead mechanism cannot tell a word describing the WRAPPER from one
    describing the WRAPPED content, so every anchor bolted onto domain-neutral English is
    placeable inside the wrapper.

    The close is to stop anchoring on a swappable noun and require co-occurrence with this
    skill's own domain-SPECIFIC verbs (`triage`/`classify`), which no other skill in this
    registry uses in its routing patterns at all. Measured after that change: 516 of 516
    combinations clean -- zero residuals, which is why this assertion is unconditional and the
    KNOWN_DUPLICATE_PATTERN_OVERLAPS allowlist (and its staleness guard) are gone rather than
    emptied. An allowlist with no entries is an invitation to add one; if a residual ever
    genuinely reappears, reintroduce the map together with the evidence for that entry.
    """
    result = _dispatch(prompt)
    assert "issue-triage" not in result.candidates, (skill, wrapper_idx, prompt, result)


@pytest.mark.parametrize(("skill", "prompt"), _positive_cases())
def test_patterns_1_and_2_do_not_capture_other_skills_bare(skill: str, prompt: str) -> None:
    """Patterns 1/2 coverage, which the wrapper sweep above does not provide.

    The routing comment claims "0 of 43 sibling positive-eval prompts match either bare" -- that
    claim had no test behind it, so a later widening of either noun set (the asymmetric noun sets
    those patterns shipped with were already fixed once) could break it silently. Bare, unwrapped
    sibling prompts are exactly the input that isolates patterns 1 and 2, since no duplicate
    wrapper is present to reach patterns 3 and 4.
    """
    result = _dispatch(prompt)
    assert "issue-triage" not in result.candidates, (skill, prompt, result)


@pytest.mark.parametrize(("skill", "prompt"), _positive_cases())
def test_triage_framed_wrapper_never_orphans_a_sibling_prompt(skill: str, prompt: str) -> None:
    """The patterns 1/2 wrapper variant: a sibling request wrapped in triage framing.

    This is the mirror of the duplicate sweep. There, issue-triage must NOT claim the prompt;
    here it legitimately may (the caller really did ask for triage), so the property under test
    is the other failure mode this fragment has now hit three times -- an exclude stripping
    issue-triage from a prompt no sibling then picks up. Whatever the owner turns out to be, it
    must exist: `no_match` is the one dispatcher outcome with no recovery path.
    """
    for wrapped in (f"Triage these incoming issues: {prompt}", f"Classify these tickets: {prompt}"):
        result = _dispatch(wrapped)
        assert result.status != "no_match", (skill, wrapped, result)
