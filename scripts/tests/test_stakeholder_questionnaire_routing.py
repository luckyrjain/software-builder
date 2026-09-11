"""Routing regression coverage for stakeholder-questionnaire."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry
from scripts.yaml_safety import load_unique_yaml_file

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


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
    """Registry-wide guard: stakeholder-questionnaire's pattern requires the literal word
    "questionnaire", confirmed unused elsewhere in the registry at spec time
    (docs/superpowers/specs/2026-09-11-two-skill-port-design.md, Global Constraint 1).
    """
    result = _dispatch(prompt)
    assert "stakeholder-questionnaire" not in result.candidates, (skill, prompt, result)
