"""Routing regression coverage for merge-conflict-analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evals.dispatcher import dispatch_prompt
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
