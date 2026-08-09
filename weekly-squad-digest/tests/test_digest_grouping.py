"""Tests for weekly-squad-digest/scripts/digest_grouping.py."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from digest_grouping import find_cross_rollup_service_pairs, normalize_service_token


class TestNormalizeServiceToken:
    def test_ignores_case_and_separators(self):
        assert normalize_service_token("API-Payments") == normalize_service_token("api_payments")

    def test_does_not_collapse_distinct_names(self):
        assert normalize_service_token("myapp") != normalize_service_token("my-app")


class TestFindCrossRollupServicePairs:
    def test_finds_normalized_match_with_different_squads(self):
        mig = [{"service": "api-payments", "squad": "payments"}]
        cost = [{"service": "API_Payments", "squad": "platform"}]
        pairs = find_cross_rollup_service_pairs(mig, cost)
        assert len(pairs) == 1
        assert pairs[0][0]["squad"] == "payments"
        assert pairs[0][1]["squad"] == "platform"

    def test_ignores_same_squad(self):
        mig = [{"service": "svc-a", "squad": "payments"}]
        cost = [{"service": "svc-a", "squad": "payments"}]
        assert find_cross_rollup_service_pairs(mig, cost) == []
