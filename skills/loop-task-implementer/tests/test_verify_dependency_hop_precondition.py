"""Tests for `verify_dependency_hop_precondition` (dependency-upgrade-review ->
loop-task-implementer handoff, C2).

See `docs/superpowers/specs/2026-10-01-c2-dependency-upgrade-executor-handoff-design.md` (revision
4) and `docs/superpowers/specs/2026-10-01-c2-dependency-upgrade-executor-handoff-change-impact.md`
("Required tests" #2). The single most important property under test: this function fails CLOSED
toward `False` on any mismatch, including `None`/empty input, and never guesses `True`.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODULE_PATH = (
    Path(__file__).resolve().parent.parent / "scripts" / "verify_dependency_hop_precondition.py"
)
_SPEC = importlib.util.spec_from_file_location("verify_dependency_hop_precondition", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
verify_dependency_hop_precondition_module = importlib.util.module_from_spec(_SPEC)
sys.modules.setdefault("verify_dependency_hop_precondition", verify_dependency_hop_precondition_module)
_SPEC.loader.exec_module(verify_dependency_hop_precondition_module)

verify_dependency_hop_precondition = (
    verify_dependency_hop_precondition_module.verify_dependency_hop_precondition
)


# ---------------------------------------------------------------------------
# Match case -> True.
# ---------------------------------------------------------------------------


def test_exact_match_returns_true():
    assert verify_dependency_hop_precondition("2.4.1", "2.4.1") == True  # noqa: E712


def test_exact_match_with_prerelease_suffix_returns_true():
    assert verify_dependency_hop_precondition("3.0.0-rc.1", "3.0.0-rc.1") == True  # noqa: E712


# ---------------------------------------------------------------------------
# Mismatch case -> False.
# ---------------------------------------------------------------------------


def test_mismatch_returns_false():
    assert verify_dependency_hop_precondition("2.4.2", "2.4.1") == False  # noqa: E712


def test_mismatch_different_major_versions_returns_false():
    assert verify_dependency_hop_precondition("3.0.0", "2.4.1") == False  # noqa: E712


def test_mismatch_is_case_sensitive_and_exact_no_semver_awareness():
    # No version-semantics-aware comparison -- "2.4.1" and "2.4.1.0" are different strings, full
    # stop, even though a semver-aware comparator might treat them as equivalent.
    assert verify_dependency_hop_precondition("2.4.1.0", "2.4.1") == False  # noqa: E712


# ---------------------------------------------------------------------------
# None / empty cases -> False (fail-closed), for either argument independently and both together.
# ---------------------------------------------------------------------------


def test_none_manifest_pinned_version_returns_false():
    assert verify_dependency_hop_precondition(None, "2.4.1") == False  # noqa: E712  # type: ignore[arg-type]


def test_none_expected_current_version_returns_false():
    assert verify_dependency_hop_precondition("2.4.1", None) == False  # noqa: E712  # type: ignore[arg-type]


def test_both_none_returns_false():
    assert verify_dependency_hop_precondition(None, None) == False  # noqa: E712  # type: ignore[arg-type]


def test_empty_manifest_pinned_version_returns_false():
    assert verify_dependency_hop_precondition("", "2.4.1") == False  # noqa: E712


def test_empty_expected_current_version_returns_false():
    assert verify_dependency_hop_precondition("2.4.1", "") == False  # noqa: E712


def test_both_empty_returns_false():
    assert verify_dependency_hop_precondition("", "") == False  # noqa: E712


def test_non_string_manifest_pinned_version_returns_false():
    assert verify_dependency_hop_precondition(241, "2.4.1") == False  # noqa: E712  # type: ignore[arg-type]
