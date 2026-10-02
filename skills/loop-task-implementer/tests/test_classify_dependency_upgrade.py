"""Tests for `classify_dependency_upgrade` (dependency-upgrade-review -> loop-task-implementer
handoff, C2).

Covers every boundary the design's own adversarial review history found a real bug or gap around --
see `docs/superpowers/specs/2026-10-01-c2-dependency-upgrade-executor-handoff-design.md` (revision 4)
and `docs/superpowers/specs/2026-10-01-c2-dependency-upgrade-executor-handoff-change-impact.md`
("Required tests" #1). The single most important property under test: this function fails CLOSED
toward `NOT_QUALIFYING` on ambiguous/malformed/unrecognized input, never fails open toward
`QUALIFYING`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "classify_dependency_upgrade.py"
)
_SPEC = importlib.util.spec_from_file_location("classify_dependency_upgrade", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
classify_dependency_upgrade_module = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("classify_dependency_upgrade", classify_dependency_upgrade_module)
_SPEC.loader.exec_module(classify_dependency_upgrade_module)

classify_dependency_upgrade = classify_dependency_upgrade_module.classify_dependency_upgrade


# ---------------------------------------------------------------------------
# All 4 canonical states, individually, as bare (already-extracted) state strings.
# ---------------------------------------------------------------------------


def test_safe_to_upgrade_bare_state_is_qualifying():
    assert classify_dependency_upgrade("Safe to upgrade") == "QUALIFYING"


def test_upgrade_with_mitigations_bare_state_is_qualifying():
    assert classify_dependency_upgrade("Upgrade with mitigations") == "QUALIFYING"


def test_do_not_upgrade_yet_bare_state_is_not_qualifying():
    assert classify_dependency_upgrade("Do not upgrade yet") == "NOT_QUALIFYING"


def test_blocked_insufficient_info_bare_state_is_not_qualifying():
    # Literal U+2014 em-dash, per report-format.md's real verdict vocabulary.
    assert classify_dependency_upgrade("Blocked — insufficient info") == "NOT_QUALIFYING"


# ---------------------------------------------------------------------------
# The full rendered "**Verdict: <state>**" line, for all four states -- proving the extraction
# regex (`^\*\*Verdict:\s*(.+?)\*\*$`) works, not just bare-state matching.
# ---------------------------------------------------------------------------


def test_rendered_verdict_line_safe_to_upgrade_is_qualifying():
    assert classify_dependency_upgrade("**Verdict: Safe to upgrade**") == "QUALIFYING"


def test_rendered_verdict_line_upgrade_with_mitigations_is_qualifying():
    assert classify_dependency_upgrade("**Verdict: Upgrade with mitigations**") == "QUALIFYING"


def test_rendered_verdict_line_do_not_upgrade_yet_is_not_qualifying():
    assert classify_dependency_upgrade("**Verdict: Do not upgrade yet**") == "NOT_QUALIFYING"


def test_rendered_verdict_line_blocked_insufficient_info_is_not_qualifying():
    assert (
        classify_dependency_upgrade("**Verdict: Blocked — insufficient info**")
        == "NOT_QUALIFYING"
    )


# ---------------------------------------------------------------------------
# The literal em-dash state as its own dedicated test: prove a plain-hyphen substitute does NOT
# match the real em-dash state -- i.e. the function does not treat "Blocked - insufficient info"
# (hyphen) as equivalent to "Blocked — insufficient info" (U+2014 em-dash).
# ---------------------------------------------------------------------------


def test_hyphen_substitute_does_not_match_em_dash_state():
    # A plain hyphen is NOT the same string as the real em-dash state -- this must fail closed to
    # NOT_QUALIFYING (an unrecognized string), not be silently treated as equivalent to the real
    # "Blocked — insufficient info" state. Either way the result is NOT_QUALIFYING here, but the
    # test exists to prove the function does not quietly normalize a hyphen into an em-dash.
    hyphen_variant = "Blocked - insufficient info"
    em_dash_variant = "Blocked — insufficient info"
    assert hyphen_variant != em_dash_variant
    assert classify_dependency_upgrade(hyphen_variant) == "NOT_QUALIFYING"
    assert classify_dependency_upgrade(em_dash_variant) == "NOT_QUALIFYING"


def test_rendered_verdict_line_with_hyphen_substitute_is_not_qualifying():
    assert (
        classify_dependency_upgrade("**Verdict: Blocked - insufficient info**")
        == "NOT_QUALIFYING"
    )


# ---------------------------------------------------------------------------
# None / empty / malformed / unrecognized-string fail-closed cases.
# ---------------------------------------------------------------------------


def test_none_verdict_is_not_qualifying():
    assert classify_dependency_upgrade(None) == "NOT_QUALIFYING"  # type: ignore[arg-type]


def test_empty_verdict_is_not_qualifying():
    assert classify_dependency_upgrade("") == "NOT_QUALIFYING"


def test_whitespace_only_verdict_is_not_qualifying():
    assert classify_dependency_upgrade("   \n\t  ") == "NOT_QUALIFYING"


def test_non_string_verdict_is_not_qualifying():
    assert classify_dependency_upgrade(12345) == "NOT_QUALIFYING"  # type: ignore[arg-type]


def test_non_string_verdict_list_is_not_qualifying():
    assert classify_dependency_upgrade(["not", "a", "string"]) == "NOT_QUALIFYING"  # type: ignore[arg-type]


def test_unrecognized_state_is_not_qualifying():
    # A plausible future fifth verdict state this report format doesn't have today -- must still
    # fail closed, never assume an unknown state is safe.
    assert classify_dependency_upgrade("Upgrade recommended with caution") == "NOT_QUALIFYING"


def test_malformed_rendered_line_missing_closing_markers_is_not_qualifying():
    # Missing the closing "**" -- does not match the extraction regex, and the raw string also
    # isn't one of the four canonical bare states, so it fails closed.
    assert classify_dependency_upgrade("**Verdict: Safe to upgrade") == "NOT_QUALIFYING"
