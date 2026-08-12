#!/usr/bin/env python3
"""Deterministic policy helpers for pr-review (recommendation matrix, caps, remote guard).

Used by pr-review/tests/test_pr_review_policy_guards.py — mirrors normative rules in
reference/review-metrics.md and reference/finding-gates.md.
"""
from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

Severity = Literal["critical", "high", "medium", "low", "none"]
RecommendationSlug = Literal["request_changes", "comment", "approve"]
RecommendationDisplay = Literal[
    "🔴 Request changes",
    "💬 Comment",
    "✅ Approve",
]


def highest_severity(severities: list[str]) -> Severity:
    order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    if not severities:
        return "none"
    best = max(severities, key=lambda s: order.get(s.lower(), 0))
    return best.lower()  # type: ignore[return-value]


def recommendation_from_highest(highest: Severity) -> tuple[RecommendationSlug, RecommendationDisplay]:
    # Display-only label for the executive summary text. SKILL.md's guardrail is absolute:
    # this skill never calls a GitLab approve/merge API. Never wire this return value into
    # an approval-triggering MCP call.
    if highest in ("critical", "high"):
        return "request_changes", "🔴 Request changes"
    if highest == "medium":
        return "comment", "💬 Comment"
    return "approve", "✅ Approve"


def apply_confidence_cap(
    proposed: Literal["high", "medium", "low"],
    *,
    single_source: bool = False,
    unresolved_contradiction: bool = False,
    assumed_only: bool = False,
) -> Literal["high", "medium", "low"]:
    """Cap per SKILL.md / evidence-quality norms."""
    if assumed_only:
        return "low"
    if proposed == "high" and (single_source or unresolved_contradiction):
        return "medium"
    return proposed


def _remote_host(url: str) -> str | None:
    """Return a normalized host for HTTPS, SSH, and SCP-style git remotes."""
    if "://" in url:
        return (urlparse(url).hostname or "").lower() or None
    match = re.match(r"(?:[^@]+@)?([^:]+):.+$", url)
    return match.group(1).lower() if match else None


def _normalized_hosts(hosts: set[str] | None) -> set[str]:
    return {host.lower() for host in (hosts or set())}


def provider_from_remote(
    url: str,
    *,
    github_hosts: set[str] | None = None,
    gitlab_hosts: set[str] | None = None,
) -> tuple[Literal["github", "gitlab"], str] | None:
    """Classify provider hosts, including configured non-conventional enterprise hosts."""
    host = _remote_host(url)
    if not host:
        return None
    if host == "github.com" or host in _normalized_hosts(github_hosts):
        return "github", host
    if host == "gitlab.com" or host in _normalized_hosts(gitlab_hosts):
        return "gitlab", host
    return None


def parse_review_url(
    url: str,
    *,
    github_hosts: set[str] | None = None,
    gitlab_hosts: set[str] | None = None,
) -> dict[str, str | int] | None:
    """Parse a GitHub PR or GitLab MR URL into a provider-neutral target."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    path = parsed.path.rstrip("/")
    github_match = re.fullmatch(r"/([^/]+)/([^/]+)/pull/(\d+)", path)
    host = parsed.hostname.lower()
    is_github_host = host == "github.com" or host in _normalized_hosts(github_hosts)
    if github_match and is_github_host and int(github_match.group(3)) > 0:
        return {
            "provider": "github",
            "host": host,
            "repository_path": f"{github_match.group(1)}/{github_match.group(2)}",
            "review_number": int(github_match.group(3)),
            "web_url": f"{parsed.scheme.lower()}://{host}{path}",
        }
    gitlab_match = re.fullmatch(r"/(.+)/-/merge_requests/(\d+)", path)
    is_gitlab_host = host == "gitlab.com" or host in _normalized_hosts(gitlab_hosts)
    if gitlab_match and is_gitlab_host and int(gitlab_match.group(2)) > 0:
        return {
            "provider": "gitlab",
            "host": host,
            "repository_path": gitlab_match.group(1),
            "review_number": int(gitlab_match.group(2)),
            "web_url": f"{parsed.scheme.lower()}://{host}{path}",
        }
    return None


def provider_from_target(
    explicit_url: str | None,
    origin_url: str,
    *,
    github_hosts: set[str] | None = None,
    gitlab_hosts: set[str] | None = None,
) -> Literal["github", "gitlab"] | None:
    """Resolve an explicit review URL, or use origin only when no URL was supplied."""
    if explicit_url:
        target = parse_review_url(
            explicit_url,
            github_hosts=github_hosts,
            gitlab_hosts=gitlab_hosts,
        )
        return target["provider"] if target else None  # type: ignore[return-value]
    remote = provider_from_remote(
        origin_url,
        github_hosts=github_hosts,
        gitlab_hosts=gitlab_hosts,
    )
    return remote[0] if remote else None


def is_github_remote(url: str) -> bool:
    provider = provider_from_remote(url)
    return provider is not None and provider[0] == "github"


def should_suppress_at_guess_gate(
    has_diff_anchor: bool,
    infers_unseen_callers: bool,
) -> bool:
    if not has_diff_anchor:
        return True
    return infers_unseen_callers


def should_suppress_at_path_gate(
    has_realistic_path: bool,
    is_non_negotiable_observable: bool,
) -> bool:
    if is_non_negotiable_observable:
        return False
    return not has_realistic_path
