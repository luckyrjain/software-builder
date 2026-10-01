"""Tests for `classify_security_finding` (security-review -> loop-task-implementer handoff, C1).

Covers every boundary the design's own 2-round adversarial review history found a real bug or gap
around -- see `docs/superpowers/specs/2026-10-01-c1-security-review-executor-handoff-design.md`
(revision 3) and `docs/superpowers/specs/2026-10-01-c1-security-review-executor-handoff-change-impact.md`
("Required tests" #1). The single most important property under test: this function fails CLOSED
toward `ROTATION_REQUIRED` on ambiguous/malformed input, never fails open toward `QUALIFYING`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "classify_security_finding.py"
)
_SPEC = importlib.util.spec_from_file_location("classify_security_finding", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
classify_security_finding_module = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("classify_security_finding", classify_security_finding_module)
_SPEC.loader.exec_module(classify_security_finding_module)

classify_security_finding = classify_security_finding_module.classify_security_finding


# ---------------------------------------------------------------------------
# Severity floor: only Critical/High/Medium (case-sensitive) ever qualify for the rotation check
# at all. Below the floor (or an unrecognized/malformed severity) -> NOT_QUALIFYING, full stop --
# this takes precedence even over rotation-shaped recommendation text (see module docstring).
# ---------------------------------------------------------------------------


def test_low_severity_is_not_qualifying():
    assert (
        classify_security_finding("Parameterize the SQL query to prevent injection.", "Low")
        == "NOT_QUALIFYING"
    )


def test_dash_severity_is_not_qualifying():
    assert (
        classify_security_finding("Parameterize the SQL query to prevent injection.", "-")
        == "NOT_QUALIFYING"
    )


def test_none_severity_is_not_qualifying():
    assert (
        classify_security_finding("Parameterize the SQL query to prevent injection.", None)
        == "NOT_QUALIFYING"
    )


def test_empty_severity_is_not_qualifying():
    assert (
        classify_security_finding("Parameterize the SQL query to prevent injection.", "")
        == "NOT_QUALIFYING"
    )


def test_severity_casing_is_case_sensitive():
    # security-review's real verdict vocabulary is "Critical | High | Medium | Low | -"
    # (skills/security-review/reference/report-format.md). Wrong casing must not qualify.
    assert (
        classify_security_finding("Parameterize the SQL query to prevent injection.", "high")
        == "NOT_QUALIFYING"
    )
    assert (
        classify_security_finding("Parameterize the SQL query to prevent injection.", "CRITICAL")
        == "NOT_QUALIFYING"
    )


def test_severity_floor_takes_precedence_over_rotation_language():
    # Rotation-shaped wording with a below-floor severity is still NOT_QUALIFYING, not
    # ROTATION_REQUIRED -- the severity check runs first and is terminal.
    assert (
        classify_security_finding("Rotate the exposed API key immediately.", "Low")
        == "NOT_QUALIFYING"
    )


# ---------------------------------------------------------------------------
# Exact keyword-match rotation cases -> ROTATION_REQUIRED. Cover all 5 action keywords against a
# spread of the 5 noun keywords, each at a qualifying severity.
# ---------------------------------------------------------------------------


def test_rotate_credential_is_rotation_required():
    assert (
        classify_security_finding("Rotate the exposed credential immediately.", "Critical")
        == "ROTATION_REQUIRED"
    )


def test_rotate_key_is_rotation_required():
    assert (
        classify_security_finding("Rotate the API key used by the webhook handler.", "High")
        == "ROTATION_REQUIRED"
    )


def test_revoke_token_is_rotation_required():
    assert (
        classify_security_finding("Revoke the leaked token and issue a replacement.", "Critical")
        == "ROTATION_REQUIRED"
    )


def test_revoke_secret_is_rotation_required():
    assert (
        classify_security_finding("Revoke the compromised secret used by this service.", "Medium")
        == "ROTATION_REQUIRED"
    )


def test_reissue_password_is_rotation_required():
    assert (
        classify_security_finding("Reissue the password for the database user.", "High")
        == "ROTATION_REQUIRED"
    )


def test_regenerate_secret_is_rotation_required():
    assert (
        classify_security_finding("Regenerate the secret used by the deploy pipeline.", "High")
        == "ROTATION_REQUIRED"
    )


def test_re_issue_key_is_rotation_required():
    assert (
        classify_security_finding("Re-issue the signing key before the next release.", "Critical")
        == "ROTATION_REQUIRED"
    )


def test_rotation_keyword_match_is_case_insensitive():
    assert (
        classify_security_finding("ROTATE the exposed CREDENTIAL immediately.", "High")
        == "ROTATION_REQUIRED"
    )


def test_rotation_keywords_outside_proximity_window_do_not_match():
    # Action and noun keyword present, but separated by more than the documented 10-word window --
    # this is a genuine boundary of the heuristic, not the headline paraphrase-evasion case below.
    far_apart = (
        "Rotate the diagram so the on-call reader can see it clearly without squinting at the "
        "the whole chart before finally noticing the word key appears"
    )
    assert classify_security_finding(far_apart, "High") == "QUALIFYING"


# ---------------------------------------------------------------------------
# The disclosed paraphrase-evasion gap (design's own Open Question 2): a Recommendation that
# describes rotation with zero keyword overlap. This function's own documented, honest behavior is
# QUALIFYING here -- NOT a false claim that the function itself closes this gap. Blocking-standard
# condition 7 (skills/loop-task-implementer/workflow/reviewer.md) is the disclosed, independent
# downstream backstop for exactly this case.
# ---------------------------------------------------------------------------


def test_paraphrase_evasion_case_is_qualifying_not_rotation_required():
    """The design's own disclosed gap: no keyword overlap, but this plainly describes rotation.

    This assertion documents the function's honestly-disclosed limitation, not a claim that it
    catches this case. Blocking-standard condition 7 exists specifically to catch a task authored
    from a finding like this one.
    """
    assert (
        classify_security_finding(
            "Request a new value from the identity provider and update the config.", "High"
        )
        == "QUALIFYING"
    )


# ---------------------------------------------------------------------------
# Ambiguous / malformed / empty / None `recommendation_text` input, at a qualifying severity ->
# ROTATION_REQUIRED (fail-closed), never QUALIFYING. This is the single most important safety
# property of this function.
# ---------------------------------------------------------------------------


def test_none_recommendation_text_is_rotation_required():
    assert classify_security_finding(None, "High") == "ROTATION_REQUIRED"


def test_empty_recommendation_text_is_rotation_required():
    assert classify_security_finding("", "Critical") == "ROTATION_REQUIRED"


def test_whitespace_only_recommendation_text_is_rotation_required():
    assert classify_security_finding("   \n\t  ", "Medium") == "ROTATION_REQUIRED"


def test_non_string_recommendation_text_is_rotation_required():
    assert classify_security_finding(12345, "High") == "ROTATION_REQUIRED"  # type: ignore[arg-type]


def test_non_string_recommendation_text_list_is_rotation_required():
    assert classify_security_finding(["not", "a", "string"], "Critical") == "ROTATION_REQUIRED"  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# A qualifying, concrete code-fix recommendation with no rotation language and a qualifying
# severity -> QUALIFYING. One case per qualifying severity level.
# ---------------------------------------------------------------------------


def test_concrete_fix_critical_severity_is_qualifying():
    assert (
        classify_security_finding(
            "Parameterize the SQL query in `get_user` to prevent injection.", "Critical"
        )
        == "QUALIFYING"
    )


def test_concrete_fix_high_severity_is_qualifying():
    assert (
        classify_security_finding(
            "Validate and allowlist the outbound host before issuing the webhook request.", "High"
        )
        == "QUALIFYING"
    )


def test_concrete_fix_medium_severity_is_qualifying():
    assert (
        classify_security_finding(
            "Escape the user-supplied value before rendering it into the HTML template.", "Medium"
        )
        == "QUALIFYING"
    )
