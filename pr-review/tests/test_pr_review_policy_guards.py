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
    parse_review_url,
    provider_from_remote,
    provider_from_target,
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

    def test_unresolved_contradiction_caps_high_to_medium(self):
        # Distinct trigger from single_source — must cap on its own, not only in combination.
        assert apply_confidence_cap("high", unresolved_contradiction=True) == "medium"
        assert apply_confidence_cap("high", single_source=False, unresolved_contradiction=True) == "medium"

    def test_assumed_only_caps_to_low(self):
        assert apply_confidence_cap("high", assumed_only=True) == "low"


class TestProviderRouting:
    def test_detects_github_dot_com_remote(self):
        assert provider_from_remote("git@github.com:acme/repo.git") == ("github", "github.com")

    def test_rejects_unconfirmed_github_prefixed_enterprise_remote(self):
        assert provider_from_remote("ssh://git@github.acme.internal/platform/payments.git") is None

    def test_detects_custom_ghes_remote_when_host_is_configured(self):
        assert provider_from_remote(
            "git@git.company.internal:platform/payments.git",
            github_hosts={"git.company.internal"},
        ) == ("github", "git.company.internal")

    def test_detects_confirmed_custom_gitlab_remote(self):
        assert provider_from_remote(
            "https://gitlab.acme.internal/platform/payments.git",
            gitlab_hosts={"gitlab.acme.internal"},
        ) == (
            "gitlab",
            "gitlab.acme.internal",
        )

    def test_rejects_unconfirmed_gitlab_prefixed_enterprise_remote(self):
        assert provider_from_remote("https://gitlab.acme.internal/platform/payments.git") is None

    def test_explicit_url_provider_wins_over_origin(self):
        assert provider_from_target(
            "https://github.com/acme/repo/pull/42",
            "https://gitlab.com/acme/repo.git",
        ) == "github"

    def test_explicit_unknown_pull_url_never_falls_back_to_gitlab_origin(self):
        assert (
            provider_from_target(
                "https://forge.company.internal/platform/payments/pull/91",
                "https://gitlab.com/acme/repo.git",
            )
            is None
        )

    def test_rejects_unconfirmed_github_prefixed_pull_request_url(self):
        assert parse_review_url("https://github.acme.internal/platform/payments/pull/91") is None

    def test_parses_confirmed_github_enterprise_pull_request_url(self):
        assert parse_review_url(
            "https://github.acme.internal/platform/payments/pull/91",
            github_hosts={"github.acme.internal"},
        ) == {
            "provider": "github",
            "host": "github.acme.internal",
            "repository_path": "platform/payments",
            "review_number": 91,
            "web_url": "https://github.acme.internal/platform/payments/pull/91",
        }

    def test_parses_standard_gitlab_merge_request_url(self):
        assert parse_review_url("https://gitlab.com/platform/payments/-/merge_requests/17") == {
            "provider": "gitlab",
            "host": "gitlab.com",
            "repository_path": "platform/payments",
            "review_number": 17,
            "web_url": "https://gitlab.com/platform/payments/-/merge_requests/17",
        }

    def test_rejects_unconfigured_custom_pull_host(self):
        assert parse_review_url("https://forge.company.internal/platform/payments/pull/91") is None

    def test_rejects_non_review_url(self):
        assert parse_review_url("https://github.com/acme/repo/issues/42") is None


class TestFindingGates:
    def test_speculative_race_suppressed_at_guess(self):
        assert should_suppress_at_guess_gate(True, infers_unseen_callers=True) is True

    def test_no_diff_anchor_suppressed_regardless_of_callers(self):
        # has_diff_anchor=False must short-circuit to suppressed even when
        # infers_unseen_callers is False — this early-return branch was untested.
        assert should_suppress_at_guess_gate(False, infers_unseen_callers=False) is True
        assert should_suppress_at_guess_gate(False, infers_unseen_callers=True) is True

    def test_has_diff_anchor_and_no_unseen_callers_not_suppressed(self):
        assert should_suppress_at_guess_gate(True, infers_unseen_callers=False) is False

    def test_guarded_null_deref_suppressed_at_path(self):
        assert should_suppress_at_path_gate(False, is_non_negotiable_observable=False) is True

    def test_secret_non_negotiable_not_suppressed(self):
        assert should_suppress_at_path_gate(False, is_non_negotiable_observable=True) is False
