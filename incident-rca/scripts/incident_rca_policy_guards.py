#!/usr/bin/env python3
"""Deterministic policy helpers for incident-rca (confidence caps, phase gates).

Mirrors normative rules in reference/evidence-quality.md and SKILL.md §Red flags.
"""
from __future__ import annotations

from typing import Literal

Confidence = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]


def apply_confidence_cap(
    proposed: Confidence,
    *,
    single_source: bool = False,
    unresolved_contradiction: bool = False,
    assumed_only: bool = False,
) -> Confidence:
    if assumed_only:
        return "LOW"
    if proposed == "HIGH" and (single_source or unresolved_contradiction):
        return "MEDIUM"
    return proposed


def should_block_phase4_ranking(
    error_signals: int,
    infra_signals: int,
) -> bool:
    return error_signals == 0 and infra_signals == 0


def should_conclude_no_defensible_root_cause(
    hypothesis_confidences: list[Confidence],
) -> bool:
    """True when no hypothesis exceeds MEDIUM after caps."""
    order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}
    if not hypothesis_confidences:
        return True
    return max(order.get(c, 0) for c in hypothesis_confidences) <= order["MEDIUM"]
