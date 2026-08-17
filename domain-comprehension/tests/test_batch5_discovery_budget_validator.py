from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_manifest_yaml import validate_manifest  # noqa: E402


def _manifest() -> dict:
    return yaml.safe_load((ROOT / "templates/manifest.yaml").read_text(encoding="utf-8"))


def test_legacy_schema_v2_manifest_without_discovery_budget_remains_valid() -> None:
    data = _manifest()
    del data["discovery_budget"]
    assert validate_manifest(data) == []


@pytest.mark.parametrize("profile", ["", "RESUME", "full", None, ["QUICK"], {"value": "QUICK"}])
def test_discovery_budget_rejects_invalid_profile(profile: object) -> None:
    data = _manifest()
    data["discovery_budget"]["profile"] = profile
    errors = validate_manifest(data)
    assert any("discovery_budget.profile" in error for error in errors)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["phases"]["p0"].__setitem__("status", {"nested": True}),
        lambda d: d.__setitem__("overall_confidence", ["not", "a", "string"]),
        lambda d: d.__setitem__("schema_version", {"nested": True}),
        lambda d: d["engagement"].__setitem__("status", {"nested": True}),
        lambda d: d["five_questions"]["q1"].__setitem__("status", {"nested": True}),
        lambda d: d["five_questions"]["q1"].__setitem__("confidence", {"nested": True}),
        lambda d: d["artifacts"][0].__setitem__("status", {"nested": True}),
        lambda d: d.__setitem__("repos", [{"name": "r", "classification": {"nested": True}}]),
        lambda d: d.__setitem__("repos", [{"name": "r", "inventory": {"nested": True}}]),
    ],
)
def test_validator_reports_errors_instead_of_crashing_on_unhashable_enum_fields(mutate) -> None:
    """A hand-edited manifest can put a mapping/list where a string enum is expected.

    The validator's job is to report that cleanly, not raise TypeError from `x not in
    some_frozenset` — unhashable values must never reach a frozenset membership test.
    """
    data = _manifest()
    mutate(data)
    errors = validate_manifest(data)
    assert errors


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


@pytest.mark.parametrize("value", [["QUICK"], "QUICK", 1, True])
def test_discovery_budget_rejects_non_object_value(value: object) -> None:
    data = _manifest()
    data["discovery_budget"] = value
    errors = validate_manifest(data)
    assert any("discovery_budget must be an object" in error for error in errors)


@pytest.mark.parametrize("field", ["limits", "consumed"])
@pytest.mark.parametrize("value", [["repositories"], "repositories", 1, None])
def test_discovery_budget_rejects_non_object_limits_or_consumed(field: str, value: object) -> None:
    data = _manifest()
    data["discovery_budget"][field] = value
    errors = validate_manifest(data)
    assert any(f"discovery_budget.{field} must be an object" in error for error in errors)


@pytest.mark.parametrize("field", ["limits", "consumed"])
def test_discovery_budget_rejects_missing_limits_or_consumed(field: str) -> None:
    data = _manifest()
    del data["discovery_budget"][field]
    errors = validate_manifest(data)
    assert any(f"discovery_budget.{field} must be an object" in error for error in errors)
