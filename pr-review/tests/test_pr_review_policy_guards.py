"""Scripted eval for pr-review policy guards (recommendation matrix, caps, gates).

Maps key scenarios from reference/pressure-tests.md to deterministic checks.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
ROOT = Path(__file__).resolve().parents[2]

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
        assert provider_from_remote("git@github.com:acme/repo.git") == (
            "github",
            "github.com:22",
        )

    def test_rejects_unconfirmed_github_prefixed_enterprise_remote(self):
        assert provider_from_remote("ssh://git@github.acme.internal/platform/payments.git") is None

    def test_detects_custom_ghes_remote_when_host_is_configured(self):
        assert provider_from_remote(
            "git@git.company.internal:platform/payments.git",
            github_hosts={"git.company.internal"},
        ) == ("github", "git.company.internal:22")

    def test_rejects_implicit_and_explicit_port_80_github_remotes(self):
        for remote in (
            "http://forge.company.internal/platform/payments.git",
            "http://forge.company.internal:80/platform/payments.git",
        ):
            assert (
                provider_from_remote(
                    remote,
                    github_hosts={"http://forge.company.internal:80"},
                )
                is None
            )

    def test_detects_confirmed_custom_gitlab_remote(self):
        assert provider_from_remote(
            "https://gitlab.acme.internal/platform/payments.git",
            gitlab_hosts={"gitlab.acme.internal"},
        ) == (
            "gitlab",
            "gitlab.acme.internal:443",
        )

    def test_rejects_unconfirmed_gitlab_prefixed_enterprise_remote(self):
        assert provider_from_remote("https://gitlab.acme.internal/platform/payments.git") is None

    def test_rejects_evil_suffix_that_only_contains_a_provider_hostname(self):
        assert provider_from_remote("https://github.com.evil.example/acme/repo.git") is None
        assert parse_review_url("https://gitlab.com.evil.example/acme/repo/-/merge_requests/1") is None

    def test_remote_authority_is_case_normalized_and_preserves_non_default_port(self):
        assert provider_from_remote(
            "ssh://git@Forge.Company.Internal:2222/platform/payments.git",
            github_hosts={"forge.company.internal:2222"},
        ) == ("github", "forge.company.internal:2222")

    def test_same_hostname_with_distinct_ports_routes_to_distinct_providers(self):
        assert provider_from_remote(
            "https://forge.company.internal:8443/platform/payments.git",
            github_hosts={"forge.company.internal:8443"},
            gitlab_hosts={"forge.company.internal:9443"},
        ) == ("github", "forge.company.internal:8443")
        assert provider_from_remote(
            "https://forge.company.internal:9443/platform/payments.git",
            github_hosts={"forge.company.internal:8443"},
            gitlab_hosts={"forge.company.internal:9443"},
        ) == ("gitlab", "forge.company.internal:9443")

    def test_wrong_port_never_falls_back_to_hostname_only_match(self):
        assert (
            provider_from_remote(
                "https://forge.company.internal:9443/platform/payments.git",
                github_hosts={"forge.company.internal:8443"},
            )
            is None
        )

    def test_overlapping_provider_authority_is_ambiguous(self):
        assert (
            provider_from_remote(
                "https://forge.company.internal:8443/platform/payments.git",
                github_hosts={"forge.company.internal:8443"},
                gitlab_hosts={"forge.company.internal:8443"},
            )
            is None
        )

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
            "authority": "github.acme.internal:443",
            "repository_path": "platform/payments",
            "review_number": 91,
            "web_url": "https://github.acme.internal/platform/payments/pull/91",
        }

    def test_rejects_implicit_and_explicit_port_80_github_review_urls(self):
        for url in (
            "http://forge.company.internal/platform/payments/pull/91",
            "http://forge.company.internal:80/platform/payments/pull/91",
        ):
            assert (
                parse_review_url(
                    url,
                    github_hosts={"http://forge.company.internal:80"},
                )
                is None
            )

    def test_http_gitlab_review_urls_remain_supported(self):
        assert parse_review_url("http://gitlab.com/platform/payments/-/merge_requests/17") == {
            "provider": "gitlab",
            "host": "gitlab.com",
            "authority": "gitlab.com:80",
            "repository_path": "platform/payments",
            "review_number": 17,
            "web_url": "http://gitlab.com/platform/payments/-/merge_requests/17",
        }

    def test_explicit_default_https_port_github_url_remains_supported(self):
        assert parse_review_url("https://github.com:443/acme/repo/pull/42") == {
            "provider": "github",
            "host": "github.com",
            "authority": "github.com:443",
            "repository_path": "acme/repo",
            "review_number": 42,
            "web_url": "https://github.com/acme/repo/pull/42",
        }

    def test_parses_standard_gitlab_merge_request_url(self):
        assert parse_review_url("https://gitlab.com/platform/payments/-/merge_requests/17") == {
            "provider": "gitlab",
            "host": "gitlab.com",
            "authority": "gitlab.com:443",
            "repository_path": "platform/payments",
            "review_number": 17,
            "web_url": "https://gitlab.com/platform/payments/-/merge_requests/17",
        }

    def test_canonical_web_url_preserves_confirmed_non_default_port(self):
        assert parse_review_url(
            "HTTPS://Forge.Company.Internal:8443/platform/payments/pull/91/",
            github_hosts={"https://forge.company.internal:8443"},
        ) == {
            "provider": "github",
            "host": "forge.company.internal",
            "authority": "forge.company.internal:8443",
            "repository_path": "platform/payments",
            "review_number": 91,
            "web_url": "https://forge.company.internal:8443/platform/payments/pull/91",
        }

    def test_review_url_rejects_confirmed_hostname_on_wrong_port(self):
        assert (
            parse_review_url(
                "https://forge.company.internal:9443/platform/payments/pull/91",
                github_hosts={"forge.company.internal:8443"},
            )
            is None
        )

    def test_review_url_overlapping_provider_authority_is_ambiguous(self):
        assert (
            parse_review_url(
                "https://forge.company.internal:8443/platform/payments/pull/91",
                github_hosts={"forge.company.internal:8443"},
                gitlab_hosts={"forge.company.internal:8443"},
            )
            is None
        )

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


class TestProviderDocumentationContracts:
    def test_phase_zero_matches_gitlab_servers_by_parsed_exact_authority(self):
        phase_zero = (ROOT / "pr-review/workflow/phase-0.md").read_text(encoding="utf-8")
        assert "parse each\n   configured `gitlab_api_url`" in phase_zero.lower()
        assert "exact normalized authority equality" in phase_zero
        assert "substring" in phase_zero
        assert "ambiguous" in phase_zero
        inputs = (ROOT / "pr-review/workflow/inputs.md").read_text(encoding="utf-8")
        adapters = (ROOT / "pr-review/reference/provider-adapters.md").read_text(encoding="utf-8")
        assert "provider, host, authority, repository_path" in inputs
        assert "authority: github.com:443" in adapters

    def test_phase_zero_requires_a_complete_provider_read_pair_before_degrading_posting(self):
        phase_zero = (ROOT / "pr-review/workflow/phase-0.md").read_text(encoding="utf-8")
        capabilities = (ROOT / "pr-review/reference/mcp-capabilities.md").read_text(encoding="utf-8")
        combined = phase_zero + capabilities
        assert "metadata-only" in combined
        assert "diff-only" in combined
        assert "complete read pair" in combined
        assert "read-only" in combined
        assert "chat-only" in combined
        assert "writes never compensate for a missing read" in combined

    def test_non_default_port_ghes_disables_all_cli_reads_without_host_only_fallback(self):
        setup = (ROOT / "pr-review/SETUP.md").read_text(encoding="utf-8")
        adapters = (ROOT / "pr-review/reference/provider-adapters.md").read_text(encoding="utf-8")
        phase_zero = (ROOT / "pr-review/workflow/phase-0.md").read_text(encoding="utf-8")
        phase_one = (ROOT / "pr-review/workflow/phase-1.md").read_text(encoding="utf-8")

        for document in (setup, adapters, phase_zero, phase_one):
            assert "non-default port" in document
            assert "CLI fallback is unavailable" in document

        for command in (
            "`gh auth status`",
            "`gh pr list`",
            "`gh pr view`",
            "`gh pr diff`",
            "`gh pr checks`",
            "`gh api`",
        ):
            assert command in phase_zero

        assert "complete GitHub App/MCP read pair" in phase_zero
        assert "metadata/current head plus changed files/diff hunks" in phase_zero
        assert "zero `gh` calls" in phase_zero
        assert "Never strip the port or make a hostname-only call" in phase_zero
        assert "zero cross-authority calls" in phase_one

    def test_http_github_urls_are_rejected_before_any_cli_or_app_routing(self):
        setup = (ROOT / "pr-review/SETUP.md").read_text(encoding="utf-8")
        adapters = (ROOT / "pr-review/reference/provider-adapters.md").read_text(encoding="utf-8")
        phase_zero = (ROOT / "pr-review/workflow/phase-0.md").read_text(encoding="utf-8")

        for document in (setup, adapters, phase_zero):
            assert "HTTP GitHub" in document
            assert "reject" in document.lower()
        assert "before any App/MCP selection or `gh` call" in " ".join(phase_zero.split())
        assert "GitLab HTTP" in adapters

    def test_provider_head_mismatch_is_zero_write_for_every_mode(self):
        posting = (ROOT / "pr-review/workflow/posting.md").read_text(encoding="utf-8")
        gitlab_inline = (ROOT / "pr-review/reference/gitlab-inline-comments.md").read_text(
            encoding="utf-8",
        )
        adapters = (ROOT / "pr-review/reference/provider-adapters.md").read_text(encoding="utf-8")
        combined = posting + gitlab_inline + adapters
        assert "`REVISION_MISMATCH`" in combined
        assert "`full`, `summary-only`, `general-only`, and draft" in combined
        assert "zero provider writes" in combined
        stale_section = gitlab_inline.split("## SHA staleness", 1)[1]
        assert "Rebuild inline positions" not in stale_section
        assert "summary-only posting" not in stale_section

    def test_github_ambiguous_write_failure_uses_readback_not_blind_retry(self):
        phase_zero = (ROOT / "pr-review/workflow/phase-0.md").read_text(encoding="utf-8")
        github_inline = (ROOT / "pr-review/reference/github-inline-comments.md").read_text(
            encoding="utf-8",
        )
        combined = phase_zero + github_inline
        assert "non-idempotent provider writes" in combined.lower()
        assert "do not blindly retry" in combined
        assert "deterministic marker and body hash" in combined
        assert "absence is proven" in combined
        assert "no duplicate POST" in " ".join(combined.split())

    def test_summary_vocabulary_is_providerized_in_all_review_modes(self):
        templates = (ROOT / "pr-review/reference/comment-templates.md").read_text(encoding="utf-8")
        incremental = (ROOT / "pr-review/reference/incremental-rerun.md").read_text(encoding="utf-8")
        modes = (ROOT / "pr-review/reference/review-modes.md").read_text(encoding="utf-8")
        examples = (ROOT / "pr-review/examples.md").read_text(encoding="utf-8")
        metrics = (ROOT / "pr-review/reference/review-metrics.md").read_text(encoding="utf-8")
        not_raised = (ROOT / "pr-review/reference/not-raised.md").read_text(encoding="utf-8")
        combined = templates + incremental + modes + examples + metrics + not_raised
        assert "not MR defects" not in combined
        assert "not PR defects" not in combined
        assert "not <review_target_noun> defects" in templates
        assert "initial, incremental, and" in templates
        assert "GitHub issue/review" in incremental
        assert "comments; GitLab MR notes/discussion threads" in incremental
        assert 'GitHub uses *"PR is merged' in modes
        assert 'GitLab uses\n*"MR is merged' in modes

    def test_github_cli_discovery_has_bound_and_truncation_stop(self):
        inputs = (ROOT / "pr-review/workflow/inputs.md").read_text(encoding="utf-8")
        assert "--limit 1000" in inputs
        assert "exactly 1000" in inputs
        assert "stop and report discovery truncation" in inputs

    def test_summary_templates_parameterize_review_target_label(self):
        templates = (ROOT / "pr-review/reference/comment-templates.md").read_text(encoding="utf-8")
        posting = (ROOT / "pr-review/workflow/posting.md").read_text(encoding="utf-8")
        assert "GitHub: `PR #<number>`" in templates
        assert "GitLab: `MR !<iid>`" in templates
        assert "Code Review — !<iid>" not in templates
        assert "Code Review (re-review) — !<iid>" not in templates
        assert "Post this review to !<iid>?" not in posting

    def test_setup_has_independent_github_and_gitlab_paths(self):
        setup = (ROOT / "pr-review/SETUP.md").read_text(encoding="utf-8")
        github = setup.split("### GitHub quickstart", 1)[1].split("### GitLab quickstart", 1)[0]
        assert "Create a GitLab PAT" not in github
        assert "mcp-gitlab" not in github
        assert "open PR" in github
        assert "### GitHub requirements" in setup
        assert "### GitLab requirements" in setup
        assert "### Use with GitHub" in setup
        assert "### Use with GitLab" in setup
        assert "### GitHub troubleshooting" in setup
        assert "### GitLab troubleshooting" in setup

    def test_public_repository_docs_describe_both_provider_read_paths(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        repository = (ROOT / "docs/REPOSITORY.md").read_text(encoding="utf-8")

        for document in (readme, repository):
            assert "GitHub/GHES or GitLab" in document
            assert "complete" in document
            assert "metadata+diff read path" in document
        assert "GitHub/GHES PR or GitLab MR review" in readme
        assert "GitHub RIGHT-side anchors and GitLab diff position mapping" in repository
        assert "configured for provider posting" in repository
        assert "pr-review | GitLab (read; write for posting)" not in repository
