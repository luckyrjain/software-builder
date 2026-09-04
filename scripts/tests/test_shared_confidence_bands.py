"""The shared confidence-band vocabulary and the one capping rule behind both skills' adapters."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def bands():
    return _load(ROOT / "docs/skill-framework/shared/confidence_bands.py", "shared_bands")


def test_bands_are_ordered_highest_first(bands) -> None:
    assert bands.BANDS == ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
    ranks = [bands.rank(band) for band in bands.BANDS]
    assert ranks == sorted(ranks, reverse=True)


def test_normalize_band_accepts_any_spelling_and_rejects_anything_else(bands) -> None:
    assert bands.normalize_band("high") == "HIGH"
    assert bands.normalize_band(" Medium ") == "MEDIUM"
    with pytest.raises(ValueError, match="unknown confidence band"):
        bands.normalize_band("very_high")
    with pytest.raises(ValueError):
        bands.normalize_band(None)


@pytest.mark.parametrize(
    ("proposed", "kwargs", "expected"),
    [
        ("HIGH", {}, "HIGH"),
        ("HIGH", {"single_source": True}, "MEDIUM"),
        ("HIGH", {"unresolved_contradiction": True}, "MEDIUM"),
        ("HIGH", {"assumed_only": True}, "LOW"),
        ("MEDIUM", {"assumed_only": True}, "LOW"),
        ("LOW", {"assumed_only": True}, "LOW"),
        # UNKNOWN is the absence of a claim, so a cap must not promote it to LOW.
        ("UNKNOWN", {"assumed_only": True}, "UNKNOWN"),
        ("HIGH", {"partial_report": True}, "MEDIUM"),
        ("LOW", {"partial_report": True}, "LOW"),
        ("HIGH", {"single_source": True, "partial_report": True}, "MEDIUM"),
    ],
)
def test_caps_only_ever_lower_confidence(bands, proposed, kwargs, expected) -> None:
    assert bands.apply_confidence_cap(proposed, **kwargs) == expected


def test_both_skill_adapters_agree_with_the_shared_rule(bands) -> None:
    """pr-review publishes lowercase bands and incident-rca UPPERCASE ones; the case lives at
    each edge, and the rule behind them is this module."""
    pr_review = _load(ROOT / "pr-review/scripts/pr_review_policy_guards.py", "prr_guards")
    incident = _load(ROOT / "incident-rca/scripts/incident_rca_policy_guards.py", "rca_guards")

    for proposed in ("high", "medium", "low"):
        for kwargs in ({}, {"single_source": True}, {"assumed_only": True}):
            expected = bands.apply_confidence_cap(proposed, **kwargs)
            assert pr_review.apply_confidence_cap(proposed, **kwargs) == expected.lower()
            assert incident.apply_confidence_cap(proposed.upper(), **kwargs) == expected


def test_footer_confidence_vocabulary_is_derived_from_the_shared_bands(bands) -> None:
    from scripts.validate_metadata_footer import (
        CONFIDENCE_VALUES,
        INVESTIGATION_CONFIDENCE_VALUES,
    )

    assert CONFIDENCE_VALUES == {"high", "medium", "low"}
    assert CONFIDENCE_VALUES == {band.lower() for band in bands.BANDS} - {"unknown"}
    # very_high has no shared band: it is footer-only.
    assert INVESTIGATION_CONFIDENCE_VALUES - CONFIDENCE_VALUES == {"very_high"}
