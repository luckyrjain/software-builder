#!/usr/bin/env python3
"""Deterministic policy helpers for incident-rca (confidence caps, phase gates).

Mirrors normative rules in reference/evidence-quality.md and SKILL.md §Red flags.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Literal

Confidence = Literal["HIGH", "MEDIUM", "LOW", "UNKNOWN"]

SKILL_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT_DIR = Path(__file__).resolve().parent
_INSTALL_MANIFEST = ".software-builder-manifest.json"
_RUNTIME_DESCRIPTION = "shared confidence-band runtime"


def _shared_runtime_loader() -> ModuleType:
    """Import shared_runtime_loader, which owns the containment policy for every module this
    script executes out of docs/skill-framework/shared/.

    Only locating the loader itself is handled here, and it needs no policy of its own: an
    installed package carries the loader beside this script (package_skill.py vendors it), so the
    lookup never leaves the package, and the install manifest is what proves a missing vendored
    copy is a packaging fault rather than an invitation to read a sibling path.
    """
    beside = _SCRIPT_DIR / "shared_runtime_loader.py"
    if beside.is_file():
        path = beside
    elif (SKILL_ROOT / _INSTALL_MANIFEST).is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {beside}")
    else:
        path = SKILL_ROOT.parent / "docs/skill-framework/shared/shared_runtime_loader.py"
    if not path.is_file():
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    spec = importlib.util.spec_from_file_location("software_builder_shared_runtime_loader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load packaged {_RUNTIME_DESCRIPTION} loader: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_confidence_bands = _shared_runtime_loader().load_shared_runtime(
    SKILL_ROOT,
    "confidence_bands",
    alias="shared_confidence_bands",
    description=_RUNTIME_DESCRIPTION,
)

# This skill already speaks the shared vocabulary's UPPERCASE spelling, so it re-exports the
# shared names directly rather than adapting at the edge.
BAND_ORDER: dict[str, int] = _confidence_bands.BAND_ORDER
apply_confidence_cap = _confidence_bands.apply_confidence_cap


def cap_partial_report_confidence(proposed: Confidence) -> Confidence:
    """Cap confidence when Phase 4 did not complete (partial/stopped report).

    Mirrors evidence-quality.md: Phase 4 incomplete / partial report → MEDIUM maximum.
    """
    return apply_confidence_cap(proposed, partial_report=True)


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
