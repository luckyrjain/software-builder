"""Routing regression coverage for domain-modeling.

Asserts every documented invocation-table row in skills/domain-modeling/examples.md
resolves the way the table claims, against the live dispatch oracle -- not just by
manual inspection of the regex. A prior review cycle found the skill's own flagship
examples didn't match its own routing patterns at all; this test exists so that
regression can't silently reappear.
"""

from pathlib import Path

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


def test_glossary_conflict_routes_to_domain_modeling() -> None:
    result = _dispatch(
        "Your glossary defines 'cancellation' as an Order state, but I mean cancelling one line item."
    )
    assert result.status == "selected", result
    assert result.owner == "domain-modeling"


def test_decision_crystallization_routes_to_domain_modeling() -> None:
    result = _dispatch(
        "We just decided: refunds always go through the original payment method, never store credit"
        " — because store credit created a reconciliation gap last quarter."
    )
    assert result.status == "selected", result
    assert result.owner == "domain-modeling"


def test_edge_case_scenario_routes_to_domain_modeling() -> None:
    result = _dispatch(
        "Stress-test the Cancellation term with an edge case: what happens if a Customer cancels an"
        " Order that's already partially shipped?"
    )
    assert result.status == "selected", result
    assert result.owner == "domain-modeling"


def test_term_sharpening_routes_to_domain_modeling() -> None:
    result = _dispatch("You're saying 'account' — do you mean the Customer or the User?")
    assert result.status == "selected", result
    assert result.owner == "domain-modeling"


def test_direct_context_edit_request_still_routes_to_domain_modeling() -> None:
    result = _dispatch("Just edit CONTEXT.md to add this term, don't bother with a report.")
    assert result.status == "selected", result
    assert result.owner == "domain-modeling"


def test_full_domain_reconstruction_does_not_route_to_domain_modeling() -> None:
    result = _dispatch("Map our entire domain model, we have no CONTEXT.md yet.")
    assert result.owner != "domain-modeling"


def test_module_interface_design_does_not_route_to_domain_modeling() -> None:
    result = _dispatch(
        "That Order-cancellation decision — now design the CancellationPolicy module's interface."
    )
    assert result.owner != "domain-modeling"


def test_architecture_scale_question_does_not_route_to_domain_modeling() -> None:
    result = _dispatch("Is our event-driven cancellation flow safe at 10x scale?")
    assert result.owner != "domain-modeling"


def test_generic_engineering_decision_without_justification_does_not_route_to_domain_modeling() -> None:
    # "we decided" alone is too broad for an ambient skill -- routine engineering chatter
    # unrelated to domain terminology or an ADR must not spuriously engage this skill.
    result = _dispatch("We decided to use PostgreSQL instead of MySQL for the new service.")
    assert result.owner != "domain-modeling"
