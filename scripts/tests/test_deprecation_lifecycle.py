from __future__ import annotations

from scripts.deprecation_lifecycle import validate_deprecation_item, validate_repository
from scripts.yaml_safety import load_unique_yaml


REQUIRED = {"deprecated_since", "replacement", "remove_after", "migration_note", "aliases"}


def _item(*, deprecated_since: str = "2026-01-01", remove_after: str = "2026-04-01") -> dict:
    return {
        "status": "deprecated",
        "deprecation": {
            "deprecated_since": deprecated_since,
            "replacement": "route.new",
            "remove_after": remove_after,
            "migration_note": "Move consumers to route.new.",
            "aliases": ["route.old"],
        },
    }


def test_repository_deprecation_lifecycle_is_valid() -> None:
    assert validate_repository() == []


def test_deprecation_requires_iso_dates() -> None:
    for invalid in ("Jan 1 2026", "20260101", "2026-1-01"):
        errors = validate_deprecation_item(
            _item(deprecated_since=invalid),
            "fixture",
            required_fields=REQUIRED,
            compatibility_window_days=90,
        )
        assert any("deprecated_since must be an ISO date" in error for error in errors)


def test_deprecation_enforces_compatibility_window() -> None:
    errors = validate_deprecation_item(
        _item(deprecated_since="2026-01-01", remove_after="2026-03-01"),
        "fixture",
        required_fields=REQUIRED,
        compatibility_window_days=90,
    )
    assert any("at least 90 days" in error for error in errors)


def test_deprecation_accepts_yaml_native_unquoted_dates() -> None:
    # PyYAML's SafeLoader auto-parses an unquoted YYYY-MM-DD scalar into a
    # datetime.date, not a str -- exercise the real loader, not Python string
    # literals, so this actually catches the type mismatch.
    data = load_unique_yaml(
        "status: deprecated\n"
        "deprecation:\n"
        "  deprecated_since: 2026-01-01\n"
        "  replacement: route.new\n"
        "  remove_after: 2026-04-01\n"
        "  migration_note: Move consumers to route.new.\n"
        "  aliases: [route.old]\n"
    )
    assert isinstance(data["deprecation"]["deprecated_since"], str) is False
    errors = validate_deprecation_item(
        data, "fixture", required_fields=REQUIRED, compatibility_window_days=90
    )
    assert errors == []


def test_deprecation_accepts_window_boundary() -> None:
    errors = validate_deprecation_item(
        _item(deprecated_since="2026-01-01", remove_after="2026-04-01"),
        "fixture",
        required_fields=REQUIRED,
        compatibility_window_days=90,
    )
    assert errors == []
