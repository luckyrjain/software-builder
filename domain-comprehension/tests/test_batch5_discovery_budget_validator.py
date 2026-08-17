from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_manifest_yaml import (  # noqa: E402
    DISCOVERY_BUDGET_DEFAULT_LIMITS,
    validate_manifest,
)


def _manifest() -> dict:
    return yaml.safe_load((ROOT / "templates/manifest.yaml").read_text(encoding="utf-8"))


def test_legacy_schema_v2_manifest_without_discovery_budget_remains_valid() -> None:
    data = _manifest()
    del data["discovery_budget"]
    assert validate_manifest(data) == []


def test_discovery_budget_required_when_discovery_phase_started() -> None:
    data = _manifest()
    del data["discovery_budget"]
    data["phases"]["session_0"]["status"] = "complete"
    data["phases"]["session_0"]["completed_at"] = "2026-08-17T00:00:00Z"
    errors = validate_manifest(data)
    assert any("discovery_budget is required" in error for error in errors)


def test_discovery_budget_required_under_strict() -> None:
    data = _manifest()
    del data["discovery_budget"]
    errors = validate_manifest(data, strict=True)
    assert any("discovery_budget is required" in error for error in errors)


@pytest.mark.parametrize("profile", ["", "RESUME", "full", None])
def test_discovery_budget_rejects_invalid_profile(profile: object) -> None:
    data = _manifest()
    data["discovery_budget"]["profile"] = profile
    errors = validate_manifest(data)
    assert any("discovery_budget.profile" in error for error in errors)


@pytest.mark.parametrize("counter", ["repositories", "search_queries", "deep_file_reads"])
def test_discovery_budget_rejects_non_positive_limits(counter: str) -> None:
    data = _manifest()
    data["discovery_budget"]["limits"][counter] = 0
    errors = validate_manifest(data)
    assert any(f"discovery_budget.limits.{counter}" in error for error in errors)


@pytest.mark.parametrize("counter", ["repositories", "search_queries", "deep_file_reads"])
def test_discovery_budget_rejects_negative_consumed(counter: str) -> None:
    data = _manifest()
    data["discovery_budget"]["consumed"][counter] = -1
    errors = validate_manifest(data)
    assert any(f"discovery_budget.consumed.{counter}" in error for error in errors)


def test_discovery_budget_rejects_consumption_over_limit() -> None:
    data = _manifest()
    data["discovery_budget"]["limits"]["repositories"] = 12
    data["discovery_budget"]["consumed"]["repositories"] = 13
    errors = validate_manifest(data)
    assert any("consumed.repositories exceeds configured limit" in error for error in errors)


def test_discovery_budget_rejects_boolean_counter_values() -> None:
    data = _manifest()
    data["discovery_budget"]["limits"]["repositories"] = True
    errors = validate_manifest(data)
    assert any("discovery_budget.limits.repositories must be an integer" in error for error in errors)


@pytest.mark.parametrize("profile", ["FULL", "DELTA", "ADD_REPO"])
def test_discovery_budget_rejects_profile_limit_mismatch(profile: str) -> None:
    data = _manifest()
    data["discovery_budget"]["profile"] = profile
    # Leave QUICK ceilings from the template — must fail for non-CUSTOM profiles.
    errors = validate_manifest(data)
    expected = DISCOVERY_BUDGET_DEFAULT_LIMITS[profile]["repositories"]
    assert any(
        f"discovery_budget.limits.repositories must equal {expected} for profile {profile}" in error
        for error in errors
    )


def test_discovery_budget_accepts_matching_full_defaults() -> None:
    data = _manifest()
    data["discovery_budget"]["profile"] = "FULL"
    data["discovery_budget"]["limits"] = dict(DISCOVERY_BUDGET_DEFAULT_LIMITS["FULL"])
    assert validate_manifest(data) == []


def test_custom_profile_allows_explicit_non_default_limits() -> None:
    data = _manifest()
    data["discovery_budget"]["profile"] = "CUSTOM"
    data["discovery_budget"]["limits"] = {
        "repositories": 7,
        "search_queries": 21,
        "deep_file_reads": 14,
    }
    assert validate_manifest(data) == []
