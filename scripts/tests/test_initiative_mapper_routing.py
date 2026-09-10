"""Routing regression coverage for initiative-mapper."""

from pathlib import Path

import pytest

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


def test_foggy_initiative_routes_to_initiative_mapper() -> None:
    result = _dispatch(
        "This 'modernize our billing system' effort is too big to scope in one sitting — map it into"
        " decision tickets."
    )
    assert result.status == "selected", result
    assert result.owner == "initiative-mapper"


def test_initiative_map_phrase_alone_routes_to_initiative_mapper() -> None:
    """`\\binitiative map\\b` is half the registered pattern set and had no coverage at all: every
    other test in this file exercises "decision tickets" phrasing, because that is what the plan's
    canonical example happens to use. This prompt deliberately contains no "decision ticket(s)".
    """
    prompt = (
        "Give me an initiative map for consolidating our three notification systems into one service."
    )
    assert "decision ticket" not in prompt.lower(), "this probe must isolate the other pattern"
    result = _dispatch(prompt)
    assert result.status == "selected", result
    assert result.owner == "initiative-mapper"


def test_mixed_readiness_request_is_still_claimed() -> None:
    """Regression guard for the two `exclude_patterns` this skill used to carry
    (`implementation[- ]ready.*PRD`, `already[- ]approved.*design`). They protected nothing --
    neither negative case reaches an exclude, since neither fires an include pattern -- and they
    orphaned this request, which went `no_match`. Reporting that one ticket already has an
    approved design is precisely what a decision-ticket map is for.
    """
    result = _dispatch(
        "Map this migration into decision tickets: moving to the new billing provider — the"
        " retry-queue ticket already has an already-approved design, the rest is still open."
    )
    assert result.status == "selected", result
    assert result.owner == "initiative-mapper"


def test_implementation_ready_prd_request_does_not_route_to_initiative_mapper() -> None:
    """Asserted against `.candidates`, not `.owner`: `DispatchResult.owner` is None for any
    non-`selected` result, so `owner != "initiative-mapper"` would pass vacuously if a future
    pattern change made initiative-mapper a false *candidate* here (status goes `ambiguous`)
    rather than the sole, wrongly `selected` owner. `research-brief`'s and `issue-triage`'s
    own routing tests found and fixed this identical assertion shape earlier this session.
    """
    result = _dispatch("Write an implementation-ready PRD for adding a dark-mode toggle to settings.")
    assert "initiative-mapper" not in result.candidates, result


def test_already_approved_design_does_not_route_to_initiative_mapper() -> None:
    """Same `.owner`-vs-`.candidates` characteristic as the test above."""
    result = _dispatch("Create the implementation plan for this already-approved design.")
    assert "initiative-mapper" not in result.candidates, result


def _positive_cases() -> list[tuple[str, str]]:
    raw = load_unique_yaml_file(ROOT / "evals" / "positive" / "cases.yaml")
    assert isinstance(raw, dict)
    return [
        (case["skill"], case["prompt"])
        for case in raw["cases"]
        if case["skill"] != "initiative-mapper"
    ]


@pytest.mark.parametrize(
    ("skill", "prompt"),
    [
        pytest.param(skill, prompt, id=skill)
        for skill, prompt in _positive_cases()
    ],
)
def test_initiative_mapper_does_not_capture_other_skills_positive_cases(skill: str, prompt: str) -> None:
    """Registry-wide guard: initiative-mapper's own patterns require the unique phrase
    "decision ticket(s)"/"initiative map", confirmed unused elsewhere in the registry at
    pre-flight time (grep -rn "decision ticket" scripts/registry/skills.d/*.yaml evals/).
    This sweep locks that invariant in permanently rather than leaving it as a one-time
    scratch verification -- if a future sibling skill's own positive case starts using this
    phrase, this test will be the first thing to notice.
    """
    result = _dispatch(prompt)
    assert "initiative-mapper" not in result.candidates, (skill, prompt, result)


@pytest.mark.parametrize(
    ("skill", "prompt"),
    [
        pytest.param(skill, prompt, id=skill)
        for skill, prompt in _positive_cases()
    ],
)
def test_initiative_map_wrapper_still_reaches_initiative_mapper(skill: str, prompt: str) -> None:
    """The mirror image of the sweep above, and the half that was missing. The sweep above proves
    the trigger phrases are never matched by accident; this one proves they are never *lost* --
    that wrapping any sibling's own vocabulary in an "initiative map" request still reaches this
    skill. It is the permanent guard on the removed `exclude_patterns`: any future exclude wide
    enough to swallow a legitimate mixed-readiness request (the `no_match` orphan this branch
    fixed) fails here on whichever sibling prompt it collides with, instead of silently costing
    real requests their owner. Deliberately asserts membership in `.candidates`, not `.owner`:
    the sibling's own patterns legitimately co-match, so the honest outcome is often `ambiguous`.
    """
    result = _dispatch(f"Give me an initiative map for this effort: {prompt}")
    assert "initiative-mapper" in result.candidates, (skill, prompt, result)
