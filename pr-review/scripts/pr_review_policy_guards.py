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


_DEFAULT_PORTS = {"http": 80, "https": 443, "ssh": 22, "git": 9418}


def _format_authority(host: str, port: int) -> str:
    rendered_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    return f"{rendered_host}:{port}"


def _parsed_url_authority(url: str) -> tuple[str, int, str] | None:
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    default_port = _DEFAULT_PORTS.get(scheme)
    host = (parsed.hostname or "").lower()
    if not host or default_port is None:
        return None
    try:
        port = parsed.port or default_port
    except ValueError:
        return None
    return host, port, _format_authority(host, port)


def _remote_authority(url: str) -> tuple[str, int, str] | None:
    """Return normalized hostname, effective port, and authority for a git remote."""
    if "://" in url:
        return _parsed_url_authority(url)
    match = re.fullmatch(r"(?:[^@/:]+@)?([^/:]+):.+", url)
    if not match:
        return None
    host = match.group(1).lower()
    return host, 22, _format_authority(host, 22)


def _configured_authorities(values: set[str] | None, *, default_port: int) -> set[str]:
    authorities: set[str] = set()
    for raw_value in values or set():
        value = raw_value.strip()
        if not value:
            continue
        if "://" in value:
            parsed = _parsed_url_authority(value)
            if parsed:
                authorities.add(parsed[2])
            continue
        parsed = urlparse(f"//{value}")
        host = (parsed.hostname or "").lower()
        if not host:
            continue
        try:
            port = parsed.port or default_port
        except ValueError:
            continue
        authorities.add(_format_authority(host, port))
    return authorities


def _provider_for_authority(
    authority: str,
    *,
    default_port: int,
    github_hosts: set[str] | None,
    gitlab_hosts: set[str] | None,
) -> Literal["github", "gitlab"] | None:
    github_authorities = _configured_authorities(github_hosts, default_port=default_port)
    gitlab_authorities = _configured_authorities(gitlab_hosts, default_port=default_port)
    github_match = authority == _format_authority("github.com", default_port) or (
        authority in github_authorities
    )
    gitlab_match = authority == _format_authority("gitlab.com", default_port) or (
        authority in gitlab_authorities
    )
    if github_match == gitlab_match:
        return None
    return "github" if github_match else "gitlab"


def provider_from_remote(
    url: str,
    *,
    github_hosts: set[str] | None = None,
    gitlab_hosts: set[str] | None = None,
) -> tuple[Literal["github", "gitlab"], str] | None:
    """Classify an exact remote authority, including configured enterprise authorities."""
    parsed = _remote_authority(url)
    if not parsed:
        return None
    host, _port, authority = parsed
    if "://" in url:
        default_port = _DEFAULT_PORTS.get(urlparse(url).scheme.lower())
        if default_port is None:
            return None
    else:
        default_port = 22
    provider = _provider_for_authority(
        authority,
        default_port=default_port,
        github_hosts=github_hosts,
        gitlab_hosts=gitlab_hosts,
    )
    return (provider, authority) if provider else None


def parse_review_url(
    url: str,
    *,
    github_hosts: set[str] | None = None,
    gitlab_hosts: set[str] | None = None,
) -> dict[str, str | int] | None:
    """Parse a GitHub PR or GitLab MR URL into a provider-neutral target."""
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    parsed_authority = _parsed_url_authority(url)
    if scheme not in {"http", "https"} or not parsed_authority:
        return None
    host, port, authority = parsed_authority
    path = parsed.path.rstrip("/")
    github_match = re.fullmatch(r"/([^/]+)/([^/]+)/pull/(\d+)", path)
    provider = _provider_for_authority(
        authority,
        default_port=_DEFAULT_PORTS[scheme],
        github_hosts=github_hosts,
        gitlab_hosts=gitlab_hosts,
    )
    canonical_host = _format_authority(host, port) if port != _DEFAULT_PORTS[scheme] else host
    if github_match and provider == "github" and int(github_match.group(3)) > 0:
        return {
            "provider": "github",
            "host": host,
            "authority": authority,
            "repository_path": f"{github_match.group(1)}/{github_match.group(2)}",
            "review_number": int(github_match.group(3)),
            "web_url": f"{scheme}://{canonical_host}{path}",
        }
    gitlab_match = re.fullmatch(r"/(.+)/-/merge_requests/(\d+)", path)
    if gitlab_match and provider == "gitlab" and int(gitlab_match.group(2)) > 0:
        return {
            "provider": "gitlab",
            "host": host,
            "authority": authority,
            "repository_path": gitlab_match.group(1),
            "review_number": int(gitlab_match.group(2)),
            "web_url": f"{scheme}://{canonical_host}{path}",
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
