#!/usr/bin/env python3
"""Deterministic policy helpers for incident-rca (confidence caps, phase gates).

Mirrors normative rules in reference/evidence-quality.md and SKILL.md §Red flags.
"""
from __future__ import annotations

from typing import Literal

Confidence = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]

BAND_ORDER: dict[str, int] = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}


def apply_confidence_cap(
    proposed: Confidence,
    *,
    single_source: bool = False,
    unresolved_contradiction: bool = False,
    assumed_only: bool = False,
    partial_report: bool = False,
) -> Confidence:
    capped: Confidence = proposed
    if assumed_only and BAND_ORDER[capped] > BAND_ORDER["LOW"]:
        capped = "LOW"
    if capped == "HIGH" and (single_source or unresolved_contradiction):
        capped = "MEDIUM"
    if partial_report:
        capped = cap_partial_report_confidence(capped)
    return capped


def cap_partial_report_confidence(proposed: Confidence) -> Confidence:
    """Cap confidence when Phase 4 did not complete (partial/stopped report).

    Mirrors evidence-quality.md: Phase 4 incomplete / partial report → MEDIUM maximum.
    """
    if BAND_ORDER[proposed] > BAND_ORDER["MEDIUM"]:
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
    if not hypothesis_confidences:
        return True
    return max(BAND_ORDER.get(c, 0) for c in hypothesis_confidences) <= BAND_ORDER["MEDIUM"]
