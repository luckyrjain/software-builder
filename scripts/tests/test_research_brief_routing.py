"""Routing regression coverage for research-brief."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest

from scripts.evals.dispatcher import DispatchResult, dispatch_prompt, dispatch_with_rules, load_routing_rules
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


@lru_cache(maxsize=1)
def _rules() -> dict[str, Any]:
    """Routing rules compiled once for the wrapper sweep below.

    `dispatch_prompt` re-reads and re-compiles routing_rules.yaml on every call, which is
    fine for the handful of literal cases but not for the ~130-prompt sweep.
    """
    return load_routing_rules(ROOT, load_registry(ROOT))


def _dispatch_cached(prompt: str) -> DispatchResult:
    return dispatch_with_rules(_rules(), prompt)


def test_research_question_routes_to_research_brief() -> None:
    result = _dispatch("Find out whether our rate-limiting approach matches current best practice, citing sources.")
    assert result.status == "selected", result
    assert result.owner == "research-brief"


def test_current_state_domain_question_does_not_route_to_research_brief() -> None:
    """Mirrors evals/negative/cases.yaml's research-brief row.

    Asserted against `candidates`, not `owner`: `DispatchResult.owner` is None for anything
    but a single-candidate `selected` result, so `owner != "research-brief"` passed
    vacuously whenever this prompt went `ambiguous` *with research-brief among the
    candidates* -- exactly the regression this test exists to catch.
    """
    result = _dispatch("Understand the existing payments service and its current-state domain and bounded contexts.")
    assert "research-brief" not in result.candidates, result
    assert result.status == "selected" and result.owner == "domain-comprehension", result


@pytest.mark.parametrize(
    "prompt",
    [
        # Anchor after the trigger phrase, and before it, for each of the three wrappers.
        "Find out whether SameSite=Lax is now the browser default, citing sources.",
        "Citing sources, find out whether SameSite=Lax is now the browser default.",
        "Investigate this question and cite your sources: does gRPC stream bidirectionally over HTTP/2?",
        "Cite your sources and investigate this question: does gRPC stream bidirectionally over HTTP/2?",
        "Research this question, citing the relevant RFCs: is JWT rotation still recommended?",
        "Citing primary sources, research the question of whether JWT rotation is still recommended.",
        "What does the ORM's documentation say about connection pool defaults?",
        "Find out whether there is prior art for this approach.",
    ],
)
def test_cited_research_phrasings_still_route_to_research_brief(prompt: str) -> None:
    """The skill's documented keywords keep working when a citation anchor is present."""
    result = _dispatch_cached(prompt)
    assert "research-brief" in result.candidates, result


@pytest.mark.parametrize(
    "prompt",
    [
        "Find out whether the deploy finished.",
        "Investigate this question about yesterday's rollout.",
        "Research this question: did last night's rollout finish?",
        "Find out whether anyone renamed the staging bucket.",
        # Vocabulary that was in the anchor list until it was proved to collide with the
        # rest of the registry's own evidence-driven phrasing. A wrapper plus one of
        # these words is still just a wrapper; re-adding any of them fails here first.
        "Find out whether this query follows database best practices.",
        "Investigate this question against the vendor's documentation and the docs we vendored.",
        "Find out whether we are following the platform team's guidance here.",
        "Investigate this question by tracing through the source code of the payment client.",
        "Research this question: does the state of the art still favour server-side sessions?",
    ],
)
def test_bare_wrapper_phrasing_alone_does_not_route_to_research_brief(prompt: str) -> None:
    """Topic-free English wrappers must not claim ownership on their own.

    "research this/the question", "find out whether" and "investigate ... question" say
    nothing about *this* skill's domain without a co-occurring citation anchor -- see the
    sweep below for what happens registry-wide when they do fire bare.
    """
    result = _dispatch_cached(prompt)
    assert "research-brief" not in result.candidates, result


def _positive_cases() -> list[tuple[str, str]]:
    raw = load_unique_yaml_file(ROOT / "evals" / "positive" / "cases.yaml")
    assert isinstance(raw, dict)
    return [
        (case["skill"], case["prompt"])
        for case in raw["cases"]
        if case["skill"] != "research-brief"
    ]


def _wrapped(prompt: str, template: str) -> str:
    lowered = prompt[0].lower() + prompt[1:] if prompt else prompt
    return template.format(prompt=prompt, lowered=lowered.rstrip(".?"))


# Every shape of "restate another skill's own trigger phrase inside a research-brief
# wrapper". Kept literal rather than generated so a failure names the exact framing.
WRAPPERS = (
    "find-out-whether-prefix::Find out whether {lowered}.",
    "investigate-this-question-prefix::Investigate this question: {prompt}",
    # Round 2 found this one missing, which is exactly why the `research ... this/the
    # ... question` pattern stayed unanchored through round 1's fix: no sweep prompt
    # ever exercised it. Every documented wrapper keyword needs a template here.
    "research-this-question-prefix::Research this question: {prompt}",
    "find-out-whether-suffix::{prompt} Find out whether that is the right call.",
)

SWEEP = [
    pytest.param(skill, _wrapped(prompt, wrapper.split("::", 1)[1]), id=f"{skill}-{wrapper.split('::', 1)[0]}")
    for skill, prompt in _positive_cases()
    for wrapper in WRAPPERS
]


@pytest.mark.parametrize(("skill", "prompt"), SWEEP)
def test_research_brief_does_not_capture_other_skills_wrapped_prompts(skill: str, prompt: str) -> None:
    """Registry-wide guard against research-brief's own routing patterns going topic-free.

    research-brief's documented keywords are generic English framings, so any other skill's
    real trigger phrase can be restated inside one. With bare `\\bfind out whether\\b` and
    `\\binvestigate\\b.*\\bquestion\\b` patterns, 126 of the wrapped prompts stopped resolving
    to their real owner and went `ambiguous` with research-brief instead; anchoring only those
    two left `\\bresearch\\b.*\\b(this|the)\\b.*\\bquestion\\b` bare, which cost 42 of the 43
    `research-this-question-prefix` prompts their owner until that wrapper was added here.
    Driving the sweep off evals/positive/cases.yaml rather than a frozen list means a skill
    added later is covered the day its positive case lands, which is what keeps this a
    registry-wide guard rather than a snapshot of the seven skills first noticed.

    Asserts on `candidates`, never on `owner`: an `ambiguous` DispatchResult's `owner` is
    None, so `owner != "research-brief"` would pass even when research-brief is one of the
    wrongly-surfaced candidates.
    """
    result = _dispatch_cached(prompt)
    assert "research-brief" not in result.candidates, result
    assert result.status == "selected" and result.owner == skill, result
