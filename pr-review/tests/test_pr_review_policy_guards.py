"""Scripted eval for pr-review policy guards (recommendation matrix, caps, gates).

Maps key scenarios from reference/pressure-tests.md to deterministic checks.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from pr_review_policy_guards import (  # noqa: E402
    apply_confidence_cap,
    highest_severity,
    is_github_remote,
    recommendation_from_highest,
    should_suppress_at_guess_gate,
    should_suppress_at_path_gate,
)


class TestRecommendationMatrix:
    def test_critical_request_changes(self):
        slug, display = recommendation_from_highest("critical")
        assert slug == "request_changes"
        assert "Request changes" in display

    def test_high_request_changes(self):
        slug, _ = recommendation_from_highest("high")
        assert slug == "request_changes"

    def test_medium_only_comment(self):
        slug, display = recommendation_from_highest("medium")
        assert slug == "comment"
        assert "Comment" in display

    def test_low_only_approve(self):
        slug, display = recommendation_from_highest("low")
        assert slug == "approve"
        assert "Approve" in display

    def test_none_approve(self):
        slug, _ = recommendation_from_highest("none")
        assert slug == "approve"

    def test_highest_among_mixed(self):
        assert highest_severity(["low", "high", "medium"]) == "high"
        assert highest_severity([]) == "none"


class TestConfidenceCaps:
    def test_single_source_caps_high_to_medium(self):
        assert apply_confidence_cap("high", single_source=True) == "medium"

    def test_assumed_only_caps_to_low(self):
        assert apply_confidence_cap("high", assumed_only=True) == "low"


class TestGithubEarlyExit:
    def test_github_remote_detected(self):
        assert is_github_remote("git@github.com:acme/repo.git")
        assert is_github_remote("https://github.com/acme/repo")

    def test_gitlab_not_github(self):
        assert not is_github_remote("https://gitlab.com/acme/repo.git")


class TestFindingGates:
    def test_speculative_race_suppressed_at_guess(self):
        assert should_suppress_at_guess_gate(True, infers_unseen_callers=True) is True

    def test_guarded_null_deref_suppressed_at_path(self):
        assert should_suppress_at_path_gate(False, is_non_negotiable_observable=False) is True

    def test_secret_non_negotiable_not_suppressed(self):
        assert should_suppress_at_path_gate(False, is_non_negotiable_observable=True) is False
