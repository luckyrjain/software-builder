#!/usr/bin/env python3
"""Deterministic policy helpers for pr-review (recommendation matrix, caps, remote guard).

Used by pr-review/tests/test_pr_review_policy_guards.py — mirrors normative rules in
reference/review-metrics.md and reference/finding-gates.md.
"""
from __future__ import annotations

from typing import Literal

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


def is_github_remote(url: str) -> bool:
    return "github.com" in url.lower()


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
