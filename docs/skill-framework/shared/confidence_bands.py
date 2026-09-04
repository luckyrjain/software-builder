#!/usr/bin/env python3
"""The confidence band vocabulary and the one rule that caps a band against evidence quality.

"Confidence band" is a first-class domain term, and the capping rule ("assumed-only evidence can
never support more than LOW; a single uncorroborated source or an unresolved contradiction can
never support HIGH") was written out independently in more than one skill, each citing the same
evidence-quality norms. A composed skill chain that dispatches several children has to compare
their confidences against each other, which is only meaningful if there is one vocabulary and one
rule behind them.

Bands are UPPERCASE here. A skill whose own documents publish lowercase (or any other spelling)
normalizes at its edge -- the serialization is a wire format, this is the type.
"""

from __future__ import annotations

from typing import Literal

Band = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]

# Highest first: the order a reader ranks them in, and the order comparisons read in.
BANDS: tuple[Band, ...] = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")

# UNKNOWN sorts below LOW: it is the absence of a claim, not a weak one.
BAND_ORDER: dict[str, int] = {"HIGH": 3, "MEDIUM": 2, "LOW": 1, "UNKNOWN": 0}


def normalize_band(value: object) -> Band:
    """Canonical UPPERCASE band for any accepted spelling. Raises ValueError on anything else."""
    if isinstance(value, str):
        candidate = value.strip().upper()
        if candidate in BAND_ORDER:
            return candidate  # type: ignore[return-value]
    raise ValueError(f"unknown confidence band {value!r} (expected one of {list(BANDS)})")


def rank(band: object) -> int:
    """Comparable rank of a band, highest first in BANDS order."""
    return BAND_ORDER[normalize_band(band)]


def apply_confidence_cap(
    proposed: object,
    *,
    single_source: bool = False,
    unresolved_contradiction: bool = False,
    assumed_only: bool = False,
    partial_report: bool = False,
) -> Band:
    """Lower `proposed` to the highest band the evidence actually supports.

    Each condition is a ceiling, never a floor: a band already at or below a ceiling is left
    alone, so the caps compose in any order and can only ever move confidence down.
    """
    capped = normalize_band(proposed)
    if assumed_only:
        capped = _cap_at(capped, "LOW")
    if capped == "HIGH" and (single_source or unresolved_contradiction):
        capped = "MEDIUM"
    if partial_report:
        capped = _cap_at(capped, "MEDIUM")
    return capped


def _cap_at(band: Band, ceiling: Band) -> Band:
    return ceiling if BAND_ORDER[band] > BAND_ORDER[ceiling] else band
