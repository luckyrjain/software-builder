"""Scripted eval for incident-rca policy guards."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from incident_rca_policy_guards import (  # noqa: E402
    apply_confidence_cap,
    should_block_phase4_ranking,
    should_conclude_no_defensible_root_cause,
)


class TestConfidenceCaps:
    def test_single_source_caps_high(self):
        assert apply_confidence_cap("HIGH", single_source=True) == "MEDIUM"

    def test_assumed_only_low(self):
        assert apply_confidence_cap("HIGH", assumed_only=True) == "LOW"

    def test_assumed_only_does_not_promote_unknown(self):
        assert apply_confidence_cap("UNKNOWN", assumed_only=True) == "UNKNOWN"

    def test_assumed_only_preserves_low(self):
        assert apply_confidence_cap("LOW", assumed_only=True) == "LOW"

    def test_assumed_only_caps_medium(self):
        assert apply_confidence_cap("MEDIUM", assumed_only=True) == "LOW"

    def test_unresolved_contradiction_caps_high(self):
        assert apply_confidence_cap("HIGH", unresolved_contradiction=True) == "MEDIUM"


class TestPhase4Gate:
    def test_block_when_no_signals(self):
        assert should_block_phase4_ranking(0, 0)

    def test_allow_with_error_signals(self):
        assert not should_block_phase4_ranking(1, 0)

    def test_allow_with_infra_only(self):
        assert not should_block_phase4_ranking(0, 1)


class TestUnknownPolicy:
    def test_all_medium_or_below(self):
        assert should_conclude_no_defensible_root_cause(["MEDIUM", "LOW"])

    def test_high_present(self):
        assert not should_conclude_no_defensible_root_cause(["HIGH", "MEDIUM"])

    def test_empty_hypotheses(self):
        assert should_conclude_no_defensible_root_cause([])
