"""Routing regression coverage for merge-conflict-analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evals.dispatcher import dispatch_prompt, dispatch_with_rules, load_routing_rules
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


# Prompts where the conflict is the object of an active request. The skill must own these.
ACTIVE_REQUESTS = [
    "There's a merge conflict on this branch — analyze it and recommend how to resolve each hunk.",
    "There's a rebase conflict I need help understanding — what does each side want?",
    "I'm stuck on a merge conflict between my feature branch and main — how do I resolve it?",
    "I have a merge conflict in src/pricing.py, help me figure out what each side was trying to do.",
    "This rebase conflict has one side removing the discount branch the other side just modified.",
    "Just resolve this merge conflict and commit it for me, I don't need a report.",
    "We have a rebase conflict blocking the release branch — what does each side want?",
    "analyze this rebase conflict please",
]

# Reproduced false positives: the phrase appears only as background — past tense, hypothetical, or
# a symptom of a question that belongs to a different domain entirely. Every one of these returned
# `no_match` (or selected another skill alone) before merge-conflict-analysis was registered, and
# the skill's original bare `\bmerge conflict\b` / `\brebase conflict\b` anchors claimed all of
# them. They are locked in here permanently so a future widening of the patterns fails loudly.
BACKGROUND_MENTIONS = [
    # past tense, the actual question is branching strategy
    "We had a nasty merge conflict during the release freeze and I want to understand whether our"
    " branching strategy is the real problem here.",
    # hypothetical future conflict, the question is code ownership
    "If two teams both refactor the auth module at once we'll get a merge conflict every sprint."
    " What's the right way to structure ownership so that stops happening?",
    # sequencing / initiative planning
    "How should we sequence these three initiatives so nobody ends up in rebase conflict hell?",
    # security audit; the conflict resolution is incidental history
    "A secret got committed and then removed during a merge conflict resolution — audit whether"
    " it's still reachable in history.",
    # engineering decision write-up
    "Write up the trade-offs of trunk-based development vs long-lived branches for our team."
    " The main pain point people cite is merge conflict frequency.",
    # onboarding documentation
    "Write a new-hire guide for this repo. Mention that new engineers usually hit their first"
    " merge conflict in the generated protobuf files.",
    # tech-debt assessment
    "Assess the tech debt in the payments module — one symptom is that every change there causes"
    " a merge conflict with someone else's work.",
    # capacity planning
    "Our CI queue is backed up; every rebase conflict retry adds another 20 minutes. Do we need"
    " more runners?",
    # already finished; the request is a diff review
    "I already fixed the merge conflict and pushed — can you sanity-check the final diff?",
]

# Realistic "conflict" vocabulary owned by sibling skills. None of these is a git merge/rebase
# conflict, and none may drag merge-conflict-analysis into its candidate set. Drawn from the
# siblings' own documented language (dependency-upgrade-review's transitive/version conflicts,
# resilience-review's conflicting state_semantic, pr-review's clean-diff phrasing).
SIBLING_CONFLICT_VOCABULARY = [
    "Do a dependency upgrade review for the lodash bump — check for transitive conflicts and CVEs.",
    "Version bump review please: does the new pin conflict with another declared constraint?",
    "Review this PR for correctness and regressions — the diff is already clean, no conflicts.",
    "The assessment_target's state_semantic conflicts with the embedded carrier's value — is this"
    " resilience review still valid?",
    "Two stakeholders gave conflicting requirements for the export feature; grill me on the plan.",
    "Our scheduled jobs keep conflicting over the same table lock — is that a resilience problem?",
]


@pytest.mark.parametrize("prompt", ACTIVE_REQUESTS)
def test_active_conflict_requests_route_to_merge_conflict_analysis(prompt: str) -> None:
    result = _dispatch(prompt)
    assert "merge-conflict-analysis" in result.candidates, (prompt, result)


def test_merge_conflict_routes_to_merge_conflict_analysis() -> None:
    result = _dispatch("There's a merge conflict on this branch — analyze it and recommend how to resolve each hunk.")
    assert result.status == "selected", result
    assert result.owner == "merge-conflict-analysis"


def test_rebase_conflict_routes_to_merge_conflict_analysis() -> None:
    result = _dispatch("There's a rebase conflict I need help understanding — what does each side want?")
    assert result.status == "selected", result
    assert result.owner == "merge-conflict-analysis"


def test_clean_pr_review_does_not_route_to_merge_conflict_analysis() -> None:
    result = _dispatch("Review this PR for correctness and regressions — the diff is already clean, no conflicts.")
    assert "merge-conflict-analysis" not in result.candidates, result


@pytest.mark.parametrize("prompt", BACKGROUND_MENTIONS)
def test_background_conflict_mentions_do_not_route_to_merge_conflict_analysis(prompt: str) -> None:
    """Reproduced false positives from the round-1 review: a merge/rebase conflict named as
    context for someone else's question is not a request to analyze a live conflict."""
    result = _dispatch(prompt)
    assert "merge-conflict-analysis" not in result.candidates, (prompt, result)


@pytest.mark.parametrize("prompt", SIBLING_CONFLICT_VOCABULARY)
def test_sibling_conflict_vocabulary_does_not_route_to_merge_conflict_analysis(prompt: str) -> None:
    result = _dispatch(prompt)
    assert "merge-conflict-analysis" not in result.candidates, (prompt, result)


# --- Round 2, Finding 1: negation inside pattern 1's gap -------------------------------------
# Pattern 1 allows up to 40 characters between its trigger phrase and the conflict noun, and a
# bare "no" fits there comfortably: "There is no merge conflict here — just review the PR" matched
# it and downgraded a clean pr-review selection to `ambiguous`. A negation guard closes it. These
# are reproduced false positives, not defensive guesses.
#
# Round 3 relocated that guard from `exclude_patterns` into the gap of patterns 1 and 3 (see
# `test_git_output_survives_a_negation_elsewhere_in_the_prompt` below and the routing comment in
# scripts/registry/skills.d/merge-conflict-analysis.yaml). The behavior these tests assert is
# unchanged; only where the guard lives changed.
NEGATED_CONFLICT_MENTIONS = [
    "There is no merge conflict here — just review the PR",
    "There's no merge conflict here — just review the PR",
    "There are no merge conflicts on this branch — just review the PR.",
    "We have no rebase conflict on this branch, so review the PR for correctness and regressions.",
]


@pytest.mark.parametrize("prompt", NEGATED_CONFLICT_MENTIONS)
def test_negated_conflict_mentions_do_not_route_to_merge_conflict_analysis(prompt: str) -> None:
    result = _dispatch(prompt)
    assert "merge-conflict-analysis" not in result.candidates, (prompt, result)


@pytest.mark.parametrize("prompt", NEGATED_CONFLICT_MENTIONS)
def test_negation_guard_never_leaves_a_prompt_ownerless(prompt: str) -> None:
    """A narrowing must never strip the only candidate and orphan the request.

    This is the failure mode issue-triage's own fragment documents at length: a narrowing that
    defers to a sibling has to leave that sibling actually holding the prompt. Every negated
    phrasing above still says "review the PR", so pr-review owns it outright.
    """
    result = _dispatch(prompt)
    assert result.status == "selected", (prompt, result)
    assert result.owner == "pr-review", (prompt, result)


@pytest.mark.parametrize(
    "prompt",
    [
        "There's a merge conflict and I'm not sure which side to keep — analyze it.",
        "This merge conflict is not something I understand — explain what both sides want.",
        "I have a rebase conflict and there is no PR for it yet; walk me through each hunk.",
    ],
)
def test_negation_elsewhere_in_the_prompt_still_routes_here(prompt: str) -> None:
    """The guard only rejects a negation *inside* the trigger-to-noun gap.

    A legitimate request that merely contains "not"/"no" somewhere else — past the conflict noun,
    or in a different clause — keeps its owner.
    """
    result = _dispatch(prompt)
    assert "merge-conflict-analysis" in result.candidates, (prompt, result)


# --- Round 3, Finding 1: the negation guard must not veto git's own output -------------------
# scripts/evals/dispatcher.py applies `exclude_patterns` as a WHOLE-PROMPT VETO over the whole
# skill (`any(include) and not any(exclude)`), not per-pattern. Round 2 put the negation guard
# there, so any prompt that paired a negated conflict mention with git's literal conflict output
# lost pattern 4 as well and fell all the way to `no_match`. All three prompts below reproduced
# that live. The guard now lives inside patterns 1 and 3 as a tempered gap, which cannot reach
# pattern 4 at all.
#
# A case-SENSITIVE exclude was the first fix proposed for this and was measured against these
# three prompts: it does not fix them. Their negations are lowercase prose, so a lowercase-only
# exclude fires exactly as before and still vetoes pattern 4.
NEGATION_PLUS_GIT_OUTPUT = [
    "I have no merge conflict locally but CI says CONFLICT (content): Merge conflict in src/a.py",
    "We did not have a merge conflict before, but now git says CONFLICT (content): Merge conflict"
    " in src/app.py",
    "There is no merge conflict according to the UI, yet: CONFLICT (content): Merge conflict in"
    " lib/x.py",
]


@pytest.mark.parametrize("prompt", NEGATION_PLUS_GIT_OUTPUT)
def test_git_output_survives_a_negation_elsewhere_in_the_prompt(prompt: str) -> None:
    result = _dispatch(prompt)
    assert result.status == "selected", (prompt, result)
    assert result.owner == "merge-conflict-analysis", (prompt, result)


def test_the_skill_declares_no_whole_prompt_exclude() -> None:
    """Structural guard on the Finding-1 fix, not a restatement of it.

    The dispatcher's exclude semantics are whole-skill, so re-introducing an `exclude_patterns`
    entry here silently reopens the pattern-4 veto above. Keep the narrowing inside the include
    patterns that actually need it.
    """
    assert _own_rule().exclude == (), _own_rule().exclude


# --- Round 2, Finding 2: git's own conflict output, pasted verbatim -------------------------
# None of patterns 1-3 recognized git's literal output, because all three key off human request
# framing and git's output has none. Pasting it is one of the most natural ways to present the
# problem, so pattern 4 matches it directly.
GIT_OWN_CONFLICT_OUTPUT = [
    "CONFLICT (content): Merge conflict in checkout.py",
    "Merge conflict in src/payment.py:12: both modified",
    "Auto-merging src/a.py\nCONFLICT (content): Merge conflict in src/a.py\n"
    "Automatic merge failed; fix conflicts and then commit the result.",
    "CONFLICT (modify/delete): src/old.py deleted in HEAD and modified in feature/x.",
    "I ran the rebase and got CONFLICT (add/add): Merge conflict in README.md",
]


@pytest.mark.parametrize("prompt", GIT_OWN_CONFLICT_OUTPUT)
def test_git_own_conflict_output_routes_to_merge_conflict_analysis(prompt: str) -> None:
    result = _dispatch(prompt)
    assert "merge-conflict-analysis" in result.candidates, (prompt, result)


def test_git_output_pattern_is_case_sensitive_and_path_anchored() -> None:
    """Pattern 4's `(?-i:...)` and its `\\S*[./]\\S*` path requirement are both load-bearing.

    The dispatcher compiles every pattern with IGNORECASE, so without the scoped `(?-i:...)`
    override a lowercase prose "merge conflict in ..." would match — and BACKGROUND_MENTIONS
    already contains "usually hit their first merge conflict in the generated protobuf files",
    a round-1 false positive this would have reopened. The path requirement closes the same hole
    from the other side: git always names a real file there.
    """
    prose_lowercase = next(p for p in BACKGROUND_MENTIONS if "merge conflict in the generated" in p)
    assert "merge-conflict-analysis" not in _dispatch(prose_lowercase).candidates
    # Capitalized, but the object is prose rather than a path: still not git's output.
    assert "merge-conflict-analysis" not in _dispatch(
        "Merge conflict in the generated protobuf files is what every new hire trips over — "
        "write the onboarding guide.",
    ).candidates


# --- Round 2, Finding 3: the accepted, documented residual ----------------------------------
# A present-tense conflict mention that is still only BACKGROUND for another domain's question
# reaches this skill. It is pinned here as a decision, not left as an unknown. See the routing
# comment in scripts/registry/skills.d/merge-conflict-analysis.yaml for the two narrowings that
# were built and measured before being rejected (habitual-framing exclude: caught 6 of 12 cases,
# missed every frequency-free one, and broke a legitimate request; resolution-verb gate: would
# drop two documented positives, including examples.md's worktree row).
PRESENT_TENSE_BACKGROUND_RESIDUAL = [
    "We have a merge conflict in the payments module right now — assess the tech debt there and"
    " tell us what to restructure.",
    "There is a merge conflict blocking the protobuf build. Write the new-hire guide so people"
    " know about it.",
    "We have a rebase conflict slowing the release train. Forecast our CI runner capacity for"
    " next quarter.",
    "We have a recurring rebase conflict every sprint — should we restructure our branching"
    " strategy?",
]


@pytest.mark.parametrize("prompt", PRESENT_TENSE_BACKGROUND_RESIDUAL)
def test_present_tense_background_mentions_are_an_accepted_residual(prompt: str) -> None:
    """Pins the CURRENT, imperfect-but-understood behavior of the residual class.

    This is not an assertion that routing here is desirable — it is an assertion that the
    behavior is known and deliberate, so a future change to it is a decision rather than an
    accident. If a later round finds a clean signal, this test is the one to update.
    """
    result = _dispatch(prompt)
    assert "merge-conflict-analysis" in result.candidates, (prompt, result)


@pytest.mark.parametrize("prompt", PRESENT_TENSE_BACKGROUND_RESIDUAL)
def test_residual_class_had_no_other_owner_to_steal_from(prompt: str) -> None:
    """Bounds the cost of THESE FOUR prompts: they were ownerless before this skill existed.

    Re-derived live rather than asserted from memory — every sibling's patterns are loaded and
    this skill's are removed. For the four entries above the outcome of the residual is therefore
    "a candidate where there was none", never "a sibling's prompt taken away".

    This does NOT generalize to the whole residual class; see
    `test_residual_downgrades_a_clean_sibling_dispatch_to_ambiguous` for the counterexample round 3
    reproduced, and the corrected bound in the routing comment.
    """
    rules = dict(load_routing_rules(ROOT, load_registry(ROOT)))
    del rules["merge-conflict-analysis"]
    assert dispatch_with_rules(rules, prompt).status == "no_match", (prompt, rules.keys())


# --- Round 3, Finding 6: the residual's real, narrower bound ---------------------------------
# Round 2 documented the residual as costless because "every residual prompt was `no_match` before
# this skill existed". That is true of the four prompts pinned above and false of the class. Each
# prompt below independently matches engineering-decision-discovery's own trigger phrases on its
# own merits, resolves to that skill ALONE with this skill's rules removed, and becomes `ambiguous`
# once they are restored — an already-working sibling dispatch degraded by this skill's residual.
#
# It is a downgrade, not a steal: engineering-decision-discovery stays in the candidate set every
# time. Two narrowings were built and measured before accepting it (both recorded in the routing
# comment): excluding engineering-decision-discovery's trigger phrases, and a cross-clause variant
# of the same. Both suppress "I have a merge conflict here — help me decide which side to keep" —
# a genuine request for THIS skill — and hand it to engineering-decision-discovery alone, trading
# `ambiguous` for a confidently wrong owner. The residual clause and the legitimate clause are
# word-for-word identical; only the referent of the decision request differs.
SIBLING_DOWNGRADE_RESIDUAL = [
    "We have a merge conflict in the payments module right now — help me decide whether to"
    " restructure the module ownership.",
    "There is a rebase conflict every time we touch the auth service. Grill me on the plan to"
    " split it up.",
    "We have a merge conflict blocking the release train — challenge my plan to move to"
    " trunk-based development.",
]


@pytest.mark.parametrize("prompt", SIBLING_DOWNGRADE_RESIDUAL)
def test_residual_downgrades_a_clean_sibling_dispatch_to_ambiguous(prompt: str) -> None:
    """Pins the corrected, honest bound on the residual's cost.

    Both halves are re-derived live so the claim stays falsifiable: without this skill's rules the
    prompt is owned outright by engineering-decision-discovery; with them it is `ambiguous`.
    """
    full = dict(load_routing_rules(ROOT, load_registry(ROOT)))
    without = {k: v for k, v in full.items() if k != "merge-conflict-analysis"}

    before = dispatch_with_rules(without, prompt)
    assert before.status == "selected", (prompt, before)
    assert before.owner == "engineering-decision-discovery", (prompt, before)

    after = dispatch_with_rules(full, prompt)
    assert after.status == "ambiguous", (prompt, after)
    assert set(after.candidates) == {"engineering-decision-discovery", "merge-conflict-analysis"}, (
        prompt,
        after,
    )


@pytest.mark.parametrize(
    "prompt",
    [
        "I have a merge conflict here — help me decide which side to keep.",
        "This merge conflict is blocking us; help me decide which side to keep.",
    ],
)
def test_a_decision_phrase_about_the_conflict_itself_still_reaches_this_skill(prompt: str) -> None:
    """Why the Finding-6 residual is not closed by excluding the sibling's trigger phrases.

    These prompts are structurally identical to `SIBLING_DOWNGRADE_RESIDUAL` — conflict clause,
    separator, decision phrase — but the decision *is* the conflict resolution, so this skill
    belongs in the candidate set. Any exclude keyed on the sibling's vocabulary drops these too.
    """
    result = _dispatch(prompt)
    assert "merge-conflict-analysis" in result.candidates, (prompt, result)


def _positive_cases() -> list[tuple[str, str]]:
    raw = load_unique_yaml_file(ROOT / "evals" / "positive" / "cases.yaml")
    assert isinstance(raw, dict)
    return [
        (case["skill"], case["prompt"])
        for case in raw["cases"]
        if case["skill"] != "merge-conflict-analysis"
    ]


@pytest.mark.parametrize(
    ("skill", "prompt"),
    [
        pytest.param(skill, prompt, id=skill)
        for skill, prompt in _positive_cases()
    ],
)
def test_merge_conflict_analysis_does_not_capture_other_skills_positive_cases(skill: str, prompt: str) -> None:
    """Registry-wide guard over the sibling positive corpus.

    On its own this sweep proves little: none of the sibling positive prompts contains the words
    "merge conflict", "rebase conflict", or even a bare "conflict", so it would pass against a
    maximally broad pattern. The real safety margin is exercised by
    `BACKGROUND_MENTIONS` (reproduced false positives) and `SIBLING_CONFLICT_VOCABULARY`
    (realistic non-git uses of "conflict" drawn from siblings' own documented language); this sweep
    is the corpus-wide backstop behind them, not the evidence by itself.
    """
    result = _dispatch(prompt)
    assert "merge-conflict-analysis" not in result.candidates, (skill, prompt, result)


def _own_rule():
    return load_routing_rules(ROOT, load_registry(ROOT))["merge-conflict-analysis"]


@pytest.mark.parametrize(
    ("skill", "prompt"),
    [
        pytest.param(skill, prompt, id=skill)
        for skill, prompt in _positive_cases()
    ],
)
def test_round2_additions_contribute_no_new_capture_over_the_sibling_corpus(skill: str, prompt: str) -> None:
    """Isolates the round-2 git-output pattern inside the registry-wide sweep.

    The sweep above passes for whole-rule reasons, so it cannot say whether the added git-output
    pattern is what is (or isn't) firing. This one checks that pattern on its own against every
    sibling positive prompt.

    The negation guard is no longer a separate exclude to check here — round 3 moved it inside
    patterns 1 and 3, where the sweep above already exercises it. `test_the_skill_declares_no_
    whole_prompt_exclude` keeps it from reappearing as a whole-skill veto.
    """
    git_output_pattern = _own_rule().include[-1]
    assert not git_output_pattern.search(prompt), (skill, prompt, git_output_pattern.pattern)
