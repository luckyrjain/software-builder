"""Tests for `classify_incident_preventive_action` (incident-rca -> loop-task-implementer handoff, C3).

Covers every boundary the design's own adversarial review history found a real bug or gap around --
see `docs/superpowers/specs/2026-10-02-c3-incident-rca-executor-handoff-design.md` (revision 5). The
single most important property under test: this function fails CLOSED toward `NOT_QUALIFYING` on
ambiguous/malformed/unrecognized input on every one of its six axes, never fails open toward
`QUALIFYING`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "classify_incident_preventive_action.py"
)
_SPEC = importlib.util.spec_from_file_location("classify_incident_preventive_action", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_module = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("classify_incident_preventive_action", _module)
_SPEC.loader.exec_module(_module)

classify = _module.classify_incident_preventive_action

GOLD_CONFIDENCE = "HIGH — deploy + error spike"


def _call(**overrides):
    args = {
        "action_source": "preventive",
        "priority": "P1",
        "confidence": GOLD_CONFIDENCE,
        "incident_class": "Software defect",
        "action_text": "Add regression test for transfer-money validation",
        "has_existing_task_branch": False,
    }
    args.update(overrides)
    return classify(**args)


# ---------------------------------------------------------------------------
# Axis 6 -- qualifying action text (all other axes valid).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Add regression test for transfer-money validation",
        "Add validation for amount field",
        "Add unit tests for amount parsing",
        "Fixing null check",
    ],
)
def test_code_level_actions_qualify(text):
    assert _call(action_text=text) == "QUALIFYING"


def test_disclosed_residual_qualifying_verb_plus_unlisted_infra_noun_still_qualifies():
    # DISCLOSED RESIDUAL (design APIs table): a qualifying verb plus an infra noun that is in none of
    # the exclusion lists classifies QUALIFYING. The keyword lists are a best-effort first gate; the
    # real control for infra changes is reviewer.md Blocking-standard condition 9 (diff paths).
    assert _call(action_text="Fix the data-store replication config") == "QUALIFYING"


@pytest.mark.parametrize(
    "text",
    [
        "Fix the WAF-rule ordering",
        "Fix the IAM-policy for the worker",
        "Fix security_group rules",
        "Fix the network-policy",
        "Fix the alerting threshold",
        "Refactoring the payment service",
        "Fix tokenizer bug",  # accepted over-match (token stem), safe direction
        "Fix retry policy in the client",  # accepted over-match (polic stem), safe direction
        "Fix the k8s liveness probe",
        "Fix the İAM role",  # Turkish dotted I: non-ASCII
        "Fix the wаf rule",  # Cyrillic a: non-ASCII
        "Fix the load balancer health check",
        "Fix the roll back procedure",
        "Fix the LoadBalancer health check",  # camelCase spelling of an exclusion phrase
        "Fix the SecurityGroup rules",
        "Fix the NetworkPolicy",
        "Fix the loadbalancer timeout",  # concatenated
        "Fix the securitygroup rule",
        "Fix the networkpolicy",
        "Fix the Roll-Back procedure",
        "Fix the load_balancer config",
        "Fix the scroll back handler",  # mid-word substring over-match, already true before squashing
        "Fix the load.balancer timeout",  # new: squashing ignores any separator, not just [\s_-]
        "Fix the network/policy",
        "Fix the security.group rule",
        "Fix the scaling config",
        "Fix the autoscaling config",
        "Fix the autoscaler threshold",
        "Fix the Terraform-managed bucket",
        "Fix the s3 bucket path",
        "Update the runbook",  # no qualifying token, excluded stem
        "Add a dashboard",
        "Add a monitor",  # no qualifying token
        "Migration fix for the schema",
        "",
        "   ",
        "Rename the variable",  # no qualifying token at all
    ],
)
def test_infra_or_non_code_actions_do_not_qualify(text):
    assert _call(action_text=text) == "NOT_QUALIFYING"


def test_action_text_201_chars_does_not_qualify():
    text = "Fix " + "a" * 197  # 201 chars total
    assert len(text) == 201
    assert _call(action_text=text) == "NOT_QUALIFYING"


def test_action_text_200_chars_is_within_the_cap():
    text = "Fix " + "a" * 196
    assert len(text) == 200
    assert _call(action_text=text) == "QUALIFYING"


@pytest.mark.parametrize("ctrl", ["\n", "\r", "\t", "\x00", "\x1b", "\x7f"])
def test_action_text_with_control_character_does_not_qualify(ctrl):
    assert _call(action_text=f"Fix null{ctrl}check") == "NOT_QUALIFYING"


def test_action_text_trailing_newline_does_not_qualify():
    assert _call(action_text="Fix null check\n") == "NOT_QUALIFYING"


def test_qualifying_side_is_whole_token_not_substring():
    # "attestation" / "protest" contain "test" but are not the token "test".
    assert _call(action_text="Review the attestation and protest handling flow") == "QUALIFYING"  # "handling"
    assert _call(action_text="Review the attestation") == "NOT_QUALIFYING"
    assert _call(action_text="Review the protest") == "NOT_QUALIFYING"


# ---------------------------------------------------------------------------
# Axis 1 -- action_source.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", ["corrective", "Preventive", " preventive", "", None, 1, ["preventive"]])
def test_action_source_other_than_exact_preventive_fails_closed(source):
    assert _call(action_source=source) == "NOT_QUALIFYING"


# ---------------------------------------------------------------------------
# Axis 2 -- priority allowlist {P1, P2}.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("priority", ["P1", "P2", " P1 ", "P2\t"])
def test_priority_allowlist_passes_with_whitespace_trim(priority):
    assert _call(priority=priority) == "QUALIFYING"


@pytest.mark.parametrize("priority", ["p0", "P0", "P0/P1", "Sev0", "", None, "p1", "P3", "Critical", "P1P2", 1])
def test_priority_outside_allowlist_fails_closed(priority):
    assert _call(priority=priority) == "NOT_QUALIFYING"


# ---------------------------------------------------------------------------
# Axis 3 -- confidence: first whitespace-delimited token of the RAW cell.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "confidence",
    [GOLD_CONFIDENCE, "HIGH", "MEDIUM", "MEDIUM — partial evidence", "  HIGH  — padded", "HIGH\tx"],
)
def test_confidence_high_or_medium_first_token_passes(confidence):
    assert _call(confidence=confidence) == "QUALIFYING"


@pytest.mark.parametrize(
    "confidence",
    ["LOW", "UNKNOWN", "high", "medium", "High", "", "   ", None, "LOW — HIGH", "HIGH—nospace", 3],
)
def test_confidence_other_values_fail_closed(confidence):
    assert _call(confidence=confidence) == "NOT_QUALIFYING"


# ---------------------------------------------------------------------------
# Axis 4 -- incident_class.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("incident_class", ["Software defect", "Deploy"])
def test_incident_class_allowlist_passes(incident_class):
    assert _call(incident_class=incident_class) == "QUALIFYING"


@pytest.mark.parametrize(
    "incident_class",
    [
        "Capacity", "Security", "Unknown", "Dependency", "Configuration", "Data quality", "Network",
        "Third-party", "deploy", "software defect", "", None, 5,
    ],
)
def test_incident_class_other_values_fail_closed(incident_class):
    assert _call(incident_class=incident_class) == "NOT_QUALIFYING"


# ---------------------------------------------------------------------------
# Axis 5 -- has_existing_task_branch: only the literal False passes.
# ---------------------------------------------------------------------------


def test_has_existing_task_branch_false_passes():
    assert _call(has_existing_task_branch=False) == "QUALIFYING"


@pytest.mark.parametrize("value", [True, None, 0, 1, "", "False", "no", [], ()])
def test_has_existing_task_branch_anything_but_literal_false_fails_closed(value):
    assert _call(has_existing_task_branch=value) == "NOT_QUALIFYING"


# ---------------------------------------------------------------------------
# Non-str arguments on every str-typed axis.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("field", ["action_source", "priority", "confidence", "incident_class", "action_text"])
@pytest.mark.parametrize("bad", [None, 0, 1.5, b"Fix null check", ["Fix"], {"a": 1}, object()])
def test_non_str_arguments_fail_closed_and_never_raise(field, bad):
    assert _call(**{field: bad}) == "NOT_QUALIFYING"


def test_all_valid_baseline_is_qualifying():
    assert _call() == "QUALIFYING"


def test_disclosed_residual_mid_token_stem_is_not_caught():
    # DISCLOSED RESIDUAL: exclusion stems match token prefixes only, so a stem embedded mid-token
    # ("rescaling" contains "scal") is not excluded. Only the four multi-word phrases match as squashed
    # substrings. Condition 9's diff-path check, not this gate, is the control for infra changes.
    assert _call(action_text="Fix the rescaling config") == "QUALIFYING"
