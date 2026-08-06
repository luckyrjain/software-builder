"""Scripted eval for squad-map policy helpers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from squad_mapping import (  # noqa: E402
    codeowners_fallback_row,
    confidence_for_codeowners_fallback,
    extract_squad_from_namespace,
    reconcile_confidence,
    should_hard_stop_missing_segment,
)


class TestExtractSquad:
    def test_segment_two(self):
        assert (
            extract_squad_from_namespace("acme/disbursement/api-disbursement", 2)
            == "disbursement"
        )

    def test_too_few_segments(self):
        assert extract_squad_from_namespace("acme/disbursement", 3) == "UNKNOWN"

    def test_segment_one(self):
        assert extract_squad_from_namespace("org/squad/repo", 1) == "org"


class TestReconcile:
    def test_match_high(self):
        conf, conflict = reconcile_confidence("payments", "Payments")
        assert conf == "HIGH"
        assert conflict is False

    def test_mismatch_medium_conflict(self):
        conf, conflict = reconcile_confidence("payments", "collections")
        assert conf == "MEDIUM"
        assert conflict is True

    def test_gitlab_only_medium(self):
        conf, conflict = reconcile_confidence("payments", None)
        assert conf == "MEDIUM"
        assert conflict is False

    def test_neither_unknown(self):
        conf, conflict = reconcile_confidence(None, None)
        assert conf == "UNKNOWN"
        assert conflict is False

    def test_never_high_on_conflict(self):
        conf, _ = reconcile_confidence("a", "b")
        assert conf != "HIGH"

    def test_fuzzy_alias_low(self):
        conf, conflict = reconcile_confidence("payments", "payments", fuzzy_alias_match=True)
        assert conf == "LOW"
        assert conflict is False

    def test_fuzzy_alias_disagreement_still_flags_conflict(self):
        conf, conflict = reconcile_confidence("payments", "collections", fuzzy_alias_match=True)
        assert conf == "LOW"
        assert conflict is True

    def test_fuzzy_alias_single_source_low(self):
        conf, conflict = reconcile_confidence("payments", None, fuzzy_alias_match=True)
        assert conf == "LOW"
        assert conflict is False

    def test_separator_insensitive_match(self):
        conf, conflict = reconcile_confidence("payments-squad", "Payments_Squad")
        assert conf == "HIGH"
        assert conflict is False

    def test_separator_insensitive_still_catches_real_mismatch(self):
        conf, conflict = reconcile_confidence("payments-squad", "collections-squad")
        assert conf == "MEDIUM"
        assert conflict is True

    def test_boundary_shift_names_not_falsely_merged(self):
        # Concatenation-based normalization would collapse both of these to
        # "paymentsteam" and falsely call them a match — token-set comparison
        # must keep them distinct.
        conf, conflict = reconcile_confidence("payments-team", "payment-steam")
        assert conf == "MEDIUM"
        assert conflict is True


class TestCodeownersFallback:
    def test_capped_at_low(self):
        assert confidence_for_codeowners_fallback() == "LOW"


class TestCodeownersFallbackRow:
    """Both GitLab and Datadog MCP unavailable — Step 7. The CODEOWNERS/git-log-derived squad guess
    must reach the structured output columns, never get overwritten with UNKNOWN once it's been
    computed (that would silently drop the only signal this fallback path exists to produce)."""

    def test_codeowners_guess_populates_gitlab_squad_not_unknown(self):
        squad, confidence, evidence = codeowners_fallback_row("payments-team")
        assert squad == "payments-team"
        assert squad != "UNKNOWN"
        assert confidence == "LOW"
        assert evidence == "CODEOWNERS"

    def test_multi_handle_codeowners_guess_also_flows_through(self):
        squad, confidence, evidence = codeowners_fallback_row("payments-team/platform-team")
        assert squad == "payments-team/platform-team"
        assert confidence == "LOW"
        assert evidence == "CODEOWNERS"

    def test_git_log_fallback_when_no_codeowners_pattern(self):
        squad, confidence, evidence = codeowners_fallback_row(None, "payments")
        assert squad == "payments"
        assert squad != "UNKNOWN"
        assert confidence == "LOW"
        assert evidence == "GIT_LOG"

    def test_codeowners_preferred_over_git_log_when_both_present(self):
        squad, _, evidence = codeowners_fallback_row("payments-team", "collections")
        assert squad == "payments-team"
        assert evidence == "CODEOWNERS"

    def test_neither_signal_is_genuinely_unknown(self):
        squad, confidence, evidence = codeowners_fallback_row(None, None)
        assert squad == "UNKNOWN"
        assert confidence == "LOW"
        assert evidence == "NONE"


class TestHardStop:
    def test_missing_segment_with_gitlab(self):
        assert should_hard_stop_missing_segment(gitlab_mcp_available=True, squad_path_segment=None)

    def test_ok_when_segment_set(self):
        assert not should_hard_stop_missing_segment(
            gitlab_mcp_available=True, squad_path_segment=2
        )

    def test_no_stop_without_gitlab(self):
        assert not should_hard_stop_missing_segment(
            gitlab_mcp_available=False, squad_path_segment=None
        )
