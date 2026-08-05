#!/usr/bin/env python3
"""Deterministic squad-mapping helpers (namespace extraction, reconciliation).

Mirrors normative rules in reference/squad-mapping.md — used by squad-map/tests/.
"""
from __future__ import annotations

import re
from typing import Literal

Confidence = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]


def extract_squad_from_namespace(namespace_path: str, squad_path_segment: int) -> str:
    """1-based index into full namespace path (split on /)."""
    if squad_path_segment < 1:
        return "UNKNOWN"
    parts = [p for p in namespace_path.strip("/").split("/") if p]
    if len(parts) < squad_path_segment:
        return "UNKNOWN"
    return parts[squad_path_segment - 1]


def _normalize(value: str) -> frozenset[str]:
    """Case- and separator-insensitive token set for squad/team name comparison.

    `payments-squad`, `payments_squad`, and `payments squad` are the same team by
    any human reading — split on non-alphanumeric separators and compare as a
    token set (not a concatenated string) so naming-convention differences
    between GitLab groups and Datadog team tags don't register as a false
    conflict. Token-set comparison (not concatenation) matters: concatenating
    `payments-team` and `payment-steam` both produce "paymentsteam" — a false
    match between two genuinely different names. Comparing {"payments","team"}
    vs {"payment","steam"} correctly keeps them distinct.
    """
    return frozenset(t for t in re.split(r"[^a-z0-9]+", value.lower()) if t)


def reconcile_confidence(
    gitlab_squad: str | None,
    datadog_team: str | None,
    *,
    fuzzy_alias_match: bool = False,
) -> tuple[Confidence, bool]:
    """Return (confidence, conflict_flag). Never HIGH when sources disagree.

    `fuzzy_alias_match` caps confidence at LOW (the alias itself is uncertain)
    but must NOT suppress a genuine disagreement between the two sources — a
    fuzzy-matched Datadog service pointing at a different team than GitLab is
    still a real conflict, just one reported at lower confidence.
    """
    g = (gitlab_squad or "").strip()
    d = (datadog_team or "").strip()
    g_known = bool(g) and g.upper() != "UNKNOWN"
    d_known = bool(d) and d.upper() != "UNKNOWN"

    if g_known and d_known:
        agree = _normalize(g) == _normalize(d)
        if fuzzy_alias_match:
            return "LOW", not agree
        if agree:
            return "HIGH", False
        return "MEDIUM", True
    if g_known or d_known:
        return ("LOW" if fuzzy_alias_match else "MEDIUM"), False
    return "UNKNOWN", False


def confidence_for_codeowners_fallback() -> Confidence:
    """CODEOWNERS / git-log fallback when both MCPs unavailable — capped at LOW."""
    return "LOW"


def should_hard_stop_missing_segment(
    *,
    gitlab_mcp_available: bool,
    squad_path_segment: int | None,
) -> bool:
    """HARD STOP when GitLab MCP is available but squad_path_segment is unset."""
    if not gitlab_mcp_available:
        return False
    return squad_path_segment is None or squad_path_segment < 1
