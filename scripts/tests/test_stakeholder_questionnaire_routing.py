"""Routing regression coverage for stakeholder-questionnaire."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evals.dispatcher import dispatch_prompt, dispatch_with_rules, load_routing_rules
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


def _own_rule():
    return load_routing_rules(ROOT, load_registry(ROOT))["stakeholder-questionnaire"]


# Prompts where the questionnaire is the object of an active request. The skill must own these.
# Every examples.md row whose "Resolves to" column is this skill's own territory appears here.
ACTIVE_REQUESTS = [
    # examples.md rows 1-4, 7, 8
    "We need to decide on retry budget for transient payment failures. Only the payments engineer"
    " responsible for it knows what we can sustain — they hold the SLA constraints and historical"
    " load data. Can you draft a questionnaire?",
    "We're blocked on whether to cache the user profile endpoint. Our caching expert (the platform"
    " team lead) knows the trade-offs we've already tried. Can you draft a questionnaire to explore"
    " this with them?",
    "I need a discovery questionnaire drafted.",
    "The database migrations are taking too long on prod. Draft a questionnaire.",
    "The questionnaire you draft shouldn't need to be sent — just tell me the answers.",
    "Draft a questionnaire for the frontend lead on whether we should adopt a new component"
    " library, given that they know our team's build-time constraints.",
    # reference/smoke-test.md's documented invocation string
    "Draft a questionnaire. decision_context: We need to decide on our retry budget for transient"
    " payment failures, but only the payments engineer responsible for it knows what our current"
    " production budget is and whether it's sustainable. recipient: the payments engineer"
    " responsible for the retry budget, who knows the current budget and SLA constraints.",
    # realistic phrasings outside the documented rows
    "Can you write a questionnaire for the DBA about our index strategy? Only they know the history.",
    "Put together a questionnaire for the security lead — we can't pick an auth model without what"
    " they know.",
    "Generate a discovery questionnaire for the vendor rep about their SLA terms.",
    "I want a questionnaire for the platform team lead on the caching trade-offs they've already tried.",
    "Prepare a questionnaire for the compliance officer covering the retention rules only they know.",
    "Draft a short discovery questionnaire for the DBA about the index history.",
    "Write a quick stakeholder questionnaire I can hand to the security lead.",
    "This decision is blocked on the frontend lead's knowledge — draft the questionnaire.",
]

# Reproduced false positives from the round-1 whole-branch review. In each, "questionnaire" is
# named only as BACKGROUND for a question that plainly belongs to another skill, and the original
# bare `\bquestionnaire\b` anchor claimed every one of them, downgrading an otherwise-clean
# sibling dispatch to `ambiguous`. Locked in permanently so a future widening fails loudly.
BACKGROUND_MENTIONS = [
    # onboarding documentation; the questionnaire is an HR-system artifact
    "Write a new-hire guide for this repo — mention that new engineers usually have to fill out the"
    " onboarding questionnaire in the HR system during their first week.",
    # cited research question; "questionnaire" is the research instrument being studied
    "Find out whether our current user-research questionnaire methodology matches best practice,"
    " citing sources for this question.",
    # PRD authoring; the questionnaire is the product feature being specified
    "Write an implementation-ready PRD for the customer-satisfaction questionnaire feature.",
    # raw-issue triage; the questionnaire page is where the reported bug lives
    "Triage these incoming bug reports — one is a broken link in the onboarding questionnaire page.",
]

# The same class widened past the four reproduced prompts: "questionnaire" naming a system,
# artifact, or codepath that a sibling skill's own question is about. None is a request for a
# discovery questionnaire and none may drag this skill into its candidate set.
SIBLING_DOMAIN_MENTIONS = [
    "Assess the tech debt in the survey module — the questionnaire renderer has three"
    " near-duplicate copies.",
    "Review this PR — it refactors the questionnaire form validation and adds two endpoints.",
    "Our questionnaire service is timing out under peak load; forecast the capacity we need next"
    " quarter.",
    "Write an RCA for last night's outage where the questionnaire service dropped submitted"
    " responses.",
    "Do a security review of the questionnaire upload endpoint — it takes user files.",
    "Diagnose why the questionnaire export test is failing on CI but passes locally.",
    "Map the domain for our research platform; the questionnaire bounded context is the messy one.",
    "Who owns the questionnaire service in this monorepo?",
    "Do a database review of the migration that adds the questionnaires table.",
    "Review the API design for the new questionnaires endpoint — pagination and versioning especially.",
]

# --- Why pattern 1's gap is a determiner plus two modifier words, not a free `{0,N}` span -------
# The first fix proposed for finding 1 paired a request verb with a free `[^.?!\n]{0,20..30}` gap.
# That closes BACKGROUND_MENTIONS but reopens the same class from the other side: the gap happily
# spans an unrelated direct object, so the verb's real object is something else entirely and
# "questionnaire" is again just a noun in passing. All 14 below matched that shape live.
VERB_TRAP_MENTIONS = [
    "We need to fix the questionnaire service before the launch — diagnose why it 500s.",
    "Make sure the questionnaire endpoint validates uploaded files — security review please.",
    "We want the questionnaire service to scale to 10k RPS; forecast the capacity.",
    "Send me a summary of the questionnaire module's tech debt.",
    "Write a spec for the questionnaire feature we scoped last week.",
    "Create a runbook for the questionnaire service's nightly export job.",
    "Generate a report on the questionnaire drop-off rate by page.",
    "Design a schema for the questionnaires table and review the indexes.",
    "Build a dashboard for the questionnaire completion funnel.",
    "I need to review the questionnaire form's accessibility before we ship.",
    "The questionnaire we send to customers has a typo — fix the template.",
    "Review the PR that changes how the questionnaire is sent to respondents.",
    "Diagnose why the questionnaire draft endpoint returns 500 under load.",
    "Our questionnaire is sent nightly by cron and the job failed — write the RCA.",
]

# --- Why pattern 1 carries a trailing negative lookahead ---------------------------------------
# The attributive compound: a request verb, a determiner, and "questionnaire" modifying the real
# head noun. The tight gap alone does not touch these — the verb IS adjacent to "questionnaire" —
# yet the thing being asked for is the service/schema/release, not a discovery questionnaire.
# All ten reproduced live against the tight-gap-only pattern.
ATTRIBUTIVE_COMPOUND_MENTIONS = [
    "We want the questionnaire service to scale to 10k RPS; forecast the capacity.",
    "Write the questionnaire service's runbook.",
    "We need the questionnaire form redesigned — do a design critique.",
    "Send the questionnaire metrics to the dashboard team.",
    "Create the questionnaire table's migration and review the indexes.",
    "Design the questionnaire schema for the new tenant model.",
    "I want the questionnaire API documented.",
    "Prepare the questionnaire release notes for Friday's deploy.",
    "We need the questionnaire microservice split out of the monolith.",
    "Write the questionnaire wizard's acceptance tests.",
]


@pytest.mark.parametrize("prompt", ACTIVE_REQUESTS)
def test_active_questionnaire_requests_route_here(prompt: str) -> None:
    result = _dispatch(prompt)
    assert "stakeholder-questionnaire" in result.candidates, (prompt, result)


def test_questionnaire_request_routes_to_stakeholder_questionnaire() -> None:
    result = _dispatch(
        "I can't decide the retry budget for this service — draft a questionnaire for the"
        " engineer responsible for it, asking what they know."
    )
    assert result.status == "selected", result
    assert result.owner == "stakeholder-questionnaire"


def test_self_answerable_decision_does_not_route_to_stakeholder_questionnaire() -> None:
    result = _dispatch("Help me decide between Postgres and DynamoDB for this service — grill me on the trade-offs.")
    assert "stakeholder-questionnaire" not in result.candidates, result


@pytest.mark.parametrize("prompt", BACKGROUND_MENTIONS)
def test_background_questionnaire_mentions_do_not_route_here(prompt: str) -> None:
    """The four false positives reproduced by the round-1 review.

    A questionnaire named as context for someone else's question is not a request to draft one.
    """
    result = _dispatch(prompt)
    assert "stakeholder-questionnaire" not in result.candidates, (prompt, result)


@pytest.mark.parametrize("prompt", BACKGROUND_MENTIONS)
def test_background_mentions_still_reach_their_real_owner(prompt: str) -> None:
    """A narrowing must not merely drop this skill — the sibling has to end up holding the prompt.

    Each of the four was `ambiguous(<sibling>, stakeholder-questionnaire)` before the fix; each is
    now that sibling outright. Re-derived live so the claim stays falsifiable.
    """
    result = _dispatch(prompt)
    assert result.status == "selected", (prompt, result)
    assert result.owner in {"new-hire-guide", "research-brief", "prd-architect", "issue-triage"}, (
        prompt,
        result,
    )


@pytest.mark.parametrize("prompt", SIBLING_DOMAIN_MENTIONS)
def test_sibling_domain_questionnaire_vocabulary_does_not_route_here(prompt: str) -> None:
    result = _dispatch(prompt)
    assert "stakeholder-questionnaire" not in result.candidates, (prompt, result)


@pytest.mark.parametrize("prompt", VERB_TRAP_MENTIONS)
def test_a_request_verb_with_an_unrelated_object_does_not_route_here(prompt: str) -> None:
    """Pins why pattern 1's gap is bounded to a determiner plus two modifier words.

    Widening it back to a free `[^.?!\\n]{0,20}` span re-captures every prompt here.
    """
    result = _dispatch(prompt)
    assert "stakeholder-questionnaire" not in result.candidates, (prompt, result)


@pytest.mark.parametrize("prompt", ATTRIBUTIVE_COMPOUND_MENTIONS)
def test_attributive_questionnaire_compounds_do_not_route_here(prompt: str) -> None:
    """Pins pattern 1's trailing negative lookahead.

    "the questionnaire service/schema/release" names a system under discussion; the artifact being
    asked for is the runbook, the migration, the release notes — never a discovery questionnaire.
    """
    result = _dispatch(prompt)
    assert "stakeholder-questionnaire" not in result.candidates, (prompt, result)


def test_plural_questionnaire_request_routes_here() -> None:
    """Round-1 Finding 6: `\\bquestionnaire\\b` never matched the plural.

    Multi-recipient phrasing is the same request, so every anchor is now `questionnaires?`.
    """
    result = _dispatch("Draft questionnaires for both the DBA and the SRE lead about the migration window.")
    assert result.status == "selected", result
    assert result.owner == "stakeholder-questionnaire", result


@pytest.mark.parametrize(
    "prompt",
    [
        "Triage these incoming bug reports — two are broken links in the onboarding questionnaires.",
        "Do a database review of the migration that adds the questionnaires table.",
        "Write an implementation-ready PRD for the customer-satisfaction questionnaires feature.",
    ],
)
def test_plural_does_not_widen_the_background_class(prompt: str) -> None:
    """The plural must not buy back any of the false positives the singular narrowing closed."""
    assert "stakeholder-questionnaire" not in _dispatch(prompt).candidates, prompt


def test_answered_questionnaire_handoff_belongs_to_prd_architect() -> None:
    """examples.md row 6, asserted rather than left undocumented.

    The row's own "Resolves to" column says `prd-architect`: the questionnaire is already answered
    and the ask is a PRD. Under the bare `\\bquestionnaire\\b` anchor this was
    `ambiguous(prd-architect, stakeholder-questionnaire)` — a downgrade of a clean sibling dispatch
    that the round-1 fix brief proposed preserving as intentional. It is not preserved: the
    narrowing repairs it, and the clean `prd-architect` selection is what the row documents.
    Stated here as a decision, so a future change to it is deliberate rather than accidental.
    """
    result = _dispatch(
        "We ran the questionnaire with the infra team and got their answers."
        " Now turn these answers into a PRD."
    )
    assert result.status == "selected", result
    assert result.owner == "prd-architect", result


def test_the_questionnaire_this_skill_would_draft_still_reaches_it() -> None:
    """examples.md row 7 (boundary rule) is the one documented positive pattern 1 cannot reach.

    The verb follows the noun ("the questionnaire you draft"), which is why pattern 2 exists. The
    prompt is a rejection case for the skill's own workflow — it never sends anything — but it must
    still route here to be rejected, rather than silently going nowhere.
    """
    result = _dispatch("The questionnaire you draft shouldn't need to be sent — just tell me the answers.")
    assert result.status == "selected", result
    assert result.owner == "stakeholder-questionnaire", result


@pytest.mark.parametrize(
    "prompt",
    [
        "The questionnaire we send to customers has a typo — fix the template.",
        "Review the PR that changes how the questionnaire is sent to respondents.",
        "Our questionnaire is sent nightly by cron and the job failed — write the RCA.",
    ],
)
def test_pattern_two_requires_the_pronoun(prompt: str) -> None:
    """Pattern 2's intervening `you|we|i` is load-bearing, not cosmetic.

    A bare reverse `questionnaire ... <verb>` window — the obvious simpler shape — captures all
    three of these, which are someone else's question about an existing questionnaire.
    """
    result = _dispatch(prompt)
    assert "stakeholder-questionnaire" not in result.candidates, (prompt, result)


def test_the_skill_declares_no_whole_prompt_exclude() -> None:
    """Structural guard, not a restatement of the fix.

    scripts/evals/dispatcher.py applies `exclude_patterns` as a WHOLE-PROMPT VETO over the entire
    skill (`any(include) and not any(exclude)`), never per-pattern — the semantics
    merge-conflict-analysis's round-3 fix had to undo after a whole-skill exclude silently vetoed
    an unrelated include pattern. Both narrowings here live inside pattern 1 for that reason.
    """
    assert _own_rule().exclude == (), _own_rule().exclude


# --- The accepted, measured residual -----------------------------------------------------------
# The head-noun list inside pattern 1's lookahead is best-effort BY DESIGN. The alternative — a
# closed-class allowlist of what may FOLLOW "questionnaire" (punctuation, prepositions, pronouns,
# clause openers) — scored identically on every corpus in this file (0 false positives, 0 missed
# positives) and was rejected on failure mode, not score: an unlisted follower there silently
# DROPS a real request ("Draft a questionnaire tailored to the platform lead"), while an unlisted
# head noun here only lets one extra candidate through. Both shapes of that residual are pinned
# below with live-derived before/after, so the cost is a stated bound rather than a guess.
RESIDUAL_OWNERLESS_BEFORE = "Write the questionnaire ingestion adapter documentation for new hires."
RESIDUAL_SIBLING_DOWNGRADE = "Write the questionnaire ingestion runbook and check our alert coverage."


def test_attributive_compound_residual_is_bounded() -> None:
    """Pins the CURRENT, imperfect-but-understood behavior of the residual class.

    "ingestion" is not in the lookahead's head-noun list, so pattern 1 still fires even though
    "questionnaire" is attributive. Both halves are re-derived live rather than asserted from
    memory: without this skill's rules the first prompt has no owner at all, so the cost there is
    "a candidate where there was none"; the second is owned outright by observability-review and
    the cost is a downgrade to `ambiguous` — never a steal, the sibling stays in the candidate set.

    If a later round finds a clean signal for attributive use, this is the test to update.
    """
    full = dict(load_routing_rules(ROOT, load_registry(ROOT)))
    without = {k: v for k, v in full.items() if k != "stakeholder-questionnaire"}

    before = dispatch_with_rules(without, RESIDUAL_OWNERLESS_BEFORE)
    assert before.status == "no_match", before
    after = dispatch_with_rules(full, RESIDUAL_OWNERLESS_BEFORE)
    assert after.candidates == ("stakeholder-questionnaire",), after

    before = dispatch_with_rules(without, RESIDUAL_SIBLING_DOWNGRADE)
    assert before.status == "selected", before
    assert before.owner == "observability-review", before
    after = dispatch_with_rules(full, RESIDUAL_SIBLING_DOWNGRADE)
    assert after.status == "ambiguous", after
    assert set(after.candidates) == {"observability-review", "stakeholder-questionnaire"}, after


def _positive_cases() -> list[tuple[str, str]]:
    raw = load_unique_yaml_file(ROOT / "evals" / "positive" / "cases.yaml")
    assert isinstance(raw, dict)
    return [
        (case["skill"], case["prompt"])
        for case in raw["cases"]
        if case["skill"] != "stakeholder-questionnaire"
    ]


@pytest.mark.parametrize(
    ("skill", "prompt"),
    [
        pytest.param(skill, prompt, id=skill)
        for skill, prompt in _positive_cases()
    ],
)
def test_stakeholder_questionnaire_does_not_capture_other_skills_positive_cases(skill: str, prompt: str) -> None:
    """Registry-wide backstop over the sibling positive corpus.

    On its own this sweep proves very little: no sibling positive prompt contains the word
    "questionnaire" at all, so it passed unchanged against the maximally broad bare
    `\\bquestionnaire\\b` anchor while every prompt in BACKGROUND_MENTIONS was being captured.
    The real safety margin lives in BACKGROUND_MENTIONS (reproduced false positives),
    SIBLING_DOMAIN_MENTIONS, VERB_TRAP_MENTIONS and ATTRIBUTIVE_COMPOUND_MENTIONS; this is the
    corpus-wide backstop behind them, never the evidence by itself.
    """
    result = _dispatch(prompt)
    assert "stakeholder-questionnaire" not in result.candidates, (skill, prompt, result)
