"""Routing regression coverage for bug-diagnosis."""

from pathlib import Path

from scripts.evals.dispatcher import dispatch_prompt
from scripts.registry.load import load_registry

ROOT = Path(__file__).resolve().parents[2]


def _dispatch(prompt: str):
    return dispatch_prompt(ROOT, load_registry(ROOT), prompt)


def test_diagnose_failing_test_routes_to_bug_diagnosis() -> None:
    result = _dispatch("Diagnose why this test is failing — root cause needed before we fix it.")
    assert result.status == "selected", result
    assert result.owner == "bug-diagnosis"


def test_production_outage_does_not_route_to_bug_diagnosis() -> None:
    # Matches bug-diagnosis's own include pattern ("diagnose this ... bug/regression") so the
    # exclude_patterns outage/error-spike carve-out is what actually suppresses it here — not a
    # prompt that never matched an include pattern to begin with.
    result = _dispatch("Diagnose this outage — is it a bug or a regression?")
    assert result.owner != "bug-diagnosis"


def test_fix_it_request_does_not_route_to_bug_diagnosis() -> None:
    # Matches bug-diagnosis's own include pattern ("diagnose this bug") so the exclude_patterns
    # "just fix it/this" carve-out is what actually suppresses it here — not a prompt that never
    # matched an include pattern to begin with.
    result = _dispatch("Diagnose this bug in the checkout flow, but just fix it while you're at it.")
    assert result.owner != "bug-diagnosis"
