"""Scripted eval for squad-map policy helpers."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from squad_mapping import (  # noqa: E402
    confidence_for_codeowners_fallback,
    extract_squad_from_namespace,
    reconcile_confidence,
    should_hard_stop_missing_segment,
)


class TestExtractSquad:
    def test_segment_two(self):
        assert (
            extract_squad_from_namespace("mpokket/disbursement/api-disbursement", 2)
            == "disbursement"
        )

    def test_too_few_segments(self):
        assert extract_squad_from_namespace("mpokket/disbursement", 3) == "UNKNOWN"

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


class TestCodeownersFallback:
    def test_capped_at_low(self):
        assert confidence_for_codeowners_fallback() == "LOW"


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
