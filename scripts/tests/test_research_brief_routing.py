"""Routing regression coverage for research-brief."""

from pathlib import Path

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


def test_research_question_routes_to_research_brief() -> None:
    result = _dispatch("Find out whether our rate-limiting approach matches current best practice, citing sources.")
    assert result.status == "selected", result
    assert result.owner == "research-brief"


def test_current_state_domain_question_does_not_route_to_research_brief() -> None:
    result = _dispatch("Understand the existing payments service and its current-state domain and bounded contexts.")
    assert result.owner != "research-brief"
