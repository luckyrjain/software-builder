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


# Round-3 review fix wave: permanent coverage for the bug-diagnosis/incident-rca root-cause
# routing regressions found in this round. These scenarios can't live in
# evals/{positive,ambiguous}/cases.yaml — scripts/evals/scenario_harness.py requires exactly one
# scenario per registered skill per dimension file, and each of those files already carries one
# bug-diagnosis and one incident-rca row -- so they're covered here instead, against the same
# live dispatcher.


def test_bare_root_cause_analysis_phrase_routes_to_incident_rca() -> None:
    # Main's pattern 1 had bare "root cause" as a standalone trigger. Task 4 (this branch)
    # replaced it with a co-occurrence-gated pattern and never restored an equivalent for
    # "root cause" with no other incident- or bug-context word nearby. Round 3 fixed this by
    # adding the spelled-out "root cause analysis" phrase (synonymous with "RCA") as a standalone
    # trigger — deliberately not bare "root cause" itself, which would make
    # test_diagnose_failing_test_routes_to_bug_diagnosis's prompt ambiguous again.
    result = _dispatch("Root cause analysis please.")
    assert result.status == "selected", result
    assert result.owner == "incident-rca"


def test_root_cause_for_incident_ticket_routes_to_incident_rca() -> None:
    result = _dispatch("Root cause for INC-4521.")
    assert result.status == "selected", result
    assert result.owner == "incident-rca"


def test_diagnose_failure_behind_incident_ticket_is_ambiguous() -> None:
    # bug-diagnosis's broad "diagnose the X failure" pattern (this test file's own first case)
    # used to be the sole owner of incident-ticket-anchored prompts that never say "root cause"
    # or "RCA"/"postmortem". incident-rca's new standalone anchor pattern (INC-/P1/P2/SLO
    # breach/on-call/consumer lag/deploy regression) makes this correctly ambiguous instead of
    # silently, wrongly sole-owned by bug-diagnosis.
    result = _dispatch("Diagnose the failure behind INC-4521.")
    assert result.status == "ambiguous", result
    assert sorted(result.candidates) == ["bug-diagnosis", "incident-rca"]
