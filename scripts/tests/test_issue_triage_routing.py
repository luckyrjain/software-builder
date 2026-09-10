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

    These excludes encode pr-review's FULL candidacy condition -- each of its two include
    patterns, guarded by a negative lookahead over its own three exclude patterns -- which is
    what makes orphaning impossible by construction: the exclude fires if and only if pr-review
    really would claim the prompt, so a stripped prompt always lands with pr-review. Two earlier
    forms both broke that. The original `merge (it|this)`/`approve` form used vocabulary
    pr-review does NOT recognise at all (the last four prompts below were `no_match` under it);
    round 2's replacement mirrored pr-review's includes but ignored its excludes, orphaning every
    in-domain triage prompt that also said "there is no PR" or "not production ready" -- see
    test_excludes_never_orphan_a_prompt_pr_review_declines.
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

    Round 3 then found the hole THIS list still had: every template above keeps
    `triage`/`classify` out of the wrapper entirely, so nothing here exercised the wrapper style
    that puts the domain VERB in the wrapper text alongside the duplicate question
    ("{sibling}. Is this a duplicate we should triage separately?"). That style collided on 43 of
    45 siblings against round 2's pattern 4. Templates 12-23 below are that family, all of the
    trailing shape -- verb strictly after the wrapped content, where it can only be a mention of
    triage, never an invocation of it. See the fragment's routing comment for why the mirror
    LEADING shape (verb before the wrapped content) is deliberately not in this list: it is an
    accepted `ambiguous`, pinned separately by
    `test_verb_first_duplicate_wrapper_may_claim_but_never_orphans`.
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
        # 12-23 (round 3): the domain VERB itself inside the wrapper, trailing the wrapped
        # content. Round 2's pattern 4 (`is this .* a duplicate .* (triage|classify)`) matched
        # every one of these on 43 of 45 siblings, because it let the verb turn up anywhere after
        # the duplicate question -- exactly the mention-not-invocation case. Pattern 4 is gone and
        # pattern 3 is anchored to the start of the prompt, so a verb that trails the wrapped
        # content can no longer route here. Both verbs, both the "is this a duplicate" and the
        # paraphrase forms, and the "triaged"/"needs triage" inflections are covered, so a future
        # edit cannot pass this sweep by keying on one surface form of the verb.
        f"{prompt} Is this a duplicate we should triage separately?",
        f"{prompt} Is this a duplicate we should classify separately?",
        f"{prompt} Is this a duplicate that needs triage?",
        f"{prompt} Is this issue a duplicate, or should we triage it on its own?",
        f"{prompt} Should we classify this as a duplicate?",
        f"{prompt} Triage question: is this a duplicate?",
        f"{prompt} Is this a duplicate? Triage it.",
        f"{prompt} Is this a duplicate? Classify it.",
        f"{prompt} Is this a duplicate of an existing ticket we should triage?",
        f"{prompt} Not sure if this is a duplicate; triage as needed.",
        f"{prompt} Is this a duplicate bug we need to classify?",
        f"{prompt} Should this be triaged as a duplicate?",
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
    failed 287 of 301 once the anchor moved just past "of". Round 2's second attempt required
    co-occurrence with this skill's domain-SPECIFIC verbs (`triage`/`classify`) in either order,
    and round 3 found the verb-last half of that (pattern 4) failing the identical way: the verb
    is placeable inside the wrapper too, so "{sibling}. Is this a duplicate we should triage
    separately?" collided on 43 of 45 siblings. The generalisation is that no anchor WORD, noun
    or verb, can tell a mention from an invocation -- but its POSITION can: an imperative leads
    its request.

    The close is therefore positional. Pattern 4 is deleted and pattern 3 is anchored to the
    start of the prompt, so a `triage`/`classify` trailing the wrapped content no longer reaches
    this skill. Measured after that change: 1080 of 1080 combinations clean across all 24
    templates -- zero residuals, which is why this assertion is unconditional and the
    KNOWN_DUPLICATE_PATTERN_OVERLAPS allowlist (and its staleness guard) are gone rather than
    emptied. An allowlist with no entries is an invitation to add one; if a residual ever
    genuinely reappears, reintroduce the map together with the evidence for that entry.

    The one shape deliberately NOT asserted here is the verb-first wrapper, which is an accepted
    `ambiguous` rather than a bug; see
    test_verb_first_duplicate_wrapper_may_claim_but_never_orphans.
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


# --- Round 3, finding A: an exclude must encode the sibling's FULL candidacy condition -------

# The two siblings issue-triage's excludes defer to, in the order their excludes appear in the
# fragment. Kept as data so the derivation below is a single rule applied to both, rather than
# two hand-written expectations that could drift apart.
_EXCLUDE_SIBLINGS = ("incident-triage-agent", "pr-review")


def _routing_rules_raw() -> dict:
    raw = load_unique_yaml_file(ROOT / "scripts" / "registry" / "routing_rules.yaml")
    assert isinstance(raw, dict)
    return raw["routes"]


def _sibling_candidacy_excludes(routes: dict, sibling: str) -> list[str]:
    """The excludes issue-triage must carry to defer exactly to `sibling`, derived from that
    sibling's own routing config.

    A sibling is a candidate for a prompt when one of its include patterns matches AND none of
    its own exclude patterns do. Deferring to it means firing on precisely that condition:
      * no excludes of its own -> its includes ARE the condition, so mirror them verbatim;
      * excludes of its own    -> guard each mirrored include with a negative lookahead over all
                                  of them, anchored at \\A so the whole prompt is inspected once.
    Round 2 applied only the first rule, to a sibling (pr-review) for which the second one
    applies -- see test_excludes_never_orphan_a_prompt_pr_review_declines for what that cost.
    """
    include = routes[sibling]["patterns"]
    exclude = routes[sibling].get("exclude_patterns") or []
    if not exclude:
        return list(include)
    guard = "|".join(f"(?:{pattern})" for pattern in exclude)
    return [rf"\A(?![\s\S]*(?:{guard}))(?=[\s\S]*(?:{pattern}))" for pattern in include]


def test_excludes_encode_each_siblings_full_candidacy_condition() -> None:
    """issue-triage's exclude list must be exactly the mechanical derivation above.

    This is the guard the fragment's prose promise needed and did not have. Round 2 wrote
    "mirroring makes orphaning impossible BY CONSTRUCTION" in a comment while the excludes
    mirrored only pr-review's include patterns and ignored pr-review's own three excludes, so
    the construction the comment described was not the one shipped. Deriving the expectation
    from the siblings' own fragments means the claim is now checked rather than asserted, and
    that it stays true if either sibling's patterns change -- including the case the current
    comment calls out explicitly, incident-triage-agent gaining an exclude_patterns list it does
    not have today.
    """
    routes = _routing_rules_raw()
    expected = [
        pattern
        for sibling in _EXCLUDE_SIBLINGS
        for pattern in _sibling_candidacy_excludes(routes, sibling)
    ]
    assert routes["issue-triage"]["exclude_patterns"] == expected


# In-domain triage requests crossed with tails that make pr-review DECLINE the prompt via its own
# exclude_patterns: "no PR"/"there is no PR", and the production-readiness phrasings. Round 2's
# include-only mirror fired on all 60, pr-review picked up none of them, and 36 went `no_match`
# with a further 24 landing on the wrong owner.
_IN_DOMAIN_TRIAGE = (
    "Triage these incoming bug reports",
    "Triage these raw issues",
    "Classify these incoming tickets by severity",
    "Triage the incoming issues from this week",
    "Classify these bugs by category",
    "Triage these incoming feature requests",
)
_PR_REVIEW_DECLINING_TAILS = (
    "there is no PR for any of them yet, so review each one for correctness",
    "there is no merge request open, but the reporter asked us to review the diff",
    "we have no PR to review for these",
    "one is a regression with no MR filed to review",
    "review the pull request situation: there is no pull request at all",
    "none of these are production ready — review the PR that touched this area",
    "the MR is not ready to release, so review it as a regression",
    "one asks whether the merge request is ready to deploy; review the diff first",
    "these aren't ready to ship; analyze the diff on the PR",
    "the reporter says without a PR we cannot review the regression",
)


@pytest.mark.parametrize(
    "prompt",
    [
        pytest.param(f"{head} — {tail}.", id=f"declines-{h}-{t}")
        for h, head in enumerate(_IN_DOMAIN_TRIAGE)
        for t, tail in enumerate(_PR_REVIEW_DECLINING_TAILS)
    ],
)
def test_excludes_never_orphan_a_prompt_pr_review_declines(prompt: str) -> None:
    """The behavioural half of the finding above: no prompt may end up owned by nobody.

    `no_match` is the one dispatcher outcome with no recovery path, which is why this asserts on
    it directly rather than on issue-triage's own presence: whether the guarded exclude keeps the
    prompt here or pr-review genuinely claims it (it does for "without a PR", where its own
    exclude needs the two words adjacent), some skill must be responsible for it.
    """
    result = _dispatch(prompt)
    assert result.status != "no_match", (prompt, result)


@pytest.mark.parametrize(
    "prompt",
    [
        pytest.param(f"{head} — {tail}.", id=f"keeps-{h}-{t}")
        for h, head in enumerate(_IN_DOMAIN_TRIAGE)
        for t, tail in enumerate(_PR_REVIEW_DECLINING_TAILS)
    ],
)
def test_pr_review_exclude_fires_only_where_pr_review_actually_claims(prompt: str) -> None:
    """The if-and-only-if property, stated as behaviour rather than as regex equality.

    For every prompt above, issue-triage keeps the request unless pr-review takes it. There is no
    third outcome: an exclude that strips this skill without the sibling stepping in is the
    orphaning bug, and it is what this branch shipped twice (the dead `tracker query` exclude,
    then the include-only pr-review mirror).
    """
    result = _dispatch(prompt)
    assert "issue-triage" in result.candidates or "pr-review" in result.candidates, (prompt, result)


# --- Round 3, finding B: the boundary between a verb MENTION and a verb INVOCATION -----------

def _verb_first_duplicate_wrappers(prompt: str) -> list[str]:
    """The mirror image of `_wrapped_duplicate`'s templates 12-23: the same verb-carrying
    wrapper, but LEADING the wrapped content instead of trailing it."""
    lowered = prompt[0].lower() + prompt[1:] if prompt else prompt
    lowered = lowered.rstrip(".?")
    return [
        f"Is this a duplicate we should triage separately? {lowered}.",
        f"Is this a duplicate we should classify on its own? {lowered}.",
        f"Is this a duplicate ticket we need to triage? {lowered}.",
        f"Before we triage anything: is this a duplicate? {lowered}.",
        f"Triage aside — is this a duplicate? {lowered}.",
    ]


@pytest.mark.parametrize(
    ("skill", "prompt"),
    [
        pytest.param(skill, wrapped, id=f"{skill}-verbfirst-{idx}")
        for skill, base_prompt in _positive_cases()
        for idx, wrapped in enumerate(_verb_first_duplicate_wrappers(base_prompt))
    ],
)
def test_verb_first_duplicate_wrapper_may_claim_but_never_orphans(skill: str, prompt: str) -> None:
    """The accepted residual, pinned so it stays a decision rather than becoming a surprise.

    Round 3's close draws its line at POSITION: an imperative leads its request, so a
    `triage`/`classify` that trails the wrapped content is a mention and must not route here
    (`_wrapped_duplicate` templates 12-23 assert exactly that), while one that leads it may. This
    is not a new concession -- `test_triage_framed_wrapper_never_orphans_a_sibling_prompt` already
    treats "Triage these incoming issues: {sibling}" as legitimately reaching this skill, and no
    regex over this pattern language can tell "Triage this:" from "Triage aside —".

    What must hold is the weaker, load-bearing property: the outcome is `ambiguous` or a single
    owner, never `no_match`. An `ambiguous` verdict reaches a human who can pick; a no-owner
    verdict reaches nobody. Tightening patterns 1/2 to remove even the ambiguity would cost the
    skill its primary trigger phrase and break the test named above, which is why round 3 stopped
    here deliberately instead of widening the fix.
    """
    result = _dispatch(prompt)
    assert result.status != "no_match", (skill, prompt, result)
