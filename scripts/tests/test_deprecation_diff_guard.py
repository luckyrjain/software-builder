from __future__ import annotations

from datetime import date
from pathlib import Path

import scripts.deprecation_diff_guard as guard
from scripts.deprecation_diff_guard import validate_removed_items


LIFECYCLE = {
    "compatibility_window_days": 90,
    "required_fields": [
        "deprecated_since",
        "replacement",
        "remove_after",
        "migration_note",
        "aliases",
    ],
}


def _deprecated(*, remove_after: str) -> dict:
    return {
        "status": "deprecated",
        "deprecation": {
            "deprecated_since": "2026-01-01",
            "replacement": "none",
            "remove_after": remove_after,
            "migration_note": "Remove after consumers migrate.",
            "aliases": [],
        },
    }


def test_policy_bootstrap_is_allowed_when_base_has_no_lifecycle_policy(monkeypatch) -> None:
    monkeypatch.setattr(guard, "_git_text", lambda root, ref, path: None)

    assert guard.validate_revision_removals(Path("."), "base", "head") == []


def test_removal_requires_prior_deprecation_in_base_revision() -> None:
    errors = validate_removed_items(
        {"stable:route.old": {"id": "route.old"}},
        {},
        LIFECYCLE,
        as_of=date(2026, 8, 16),
    )

    assert errors == [
        "error: stable:route.old: removal requires deprecation in the base revision before deletion"
    ]


def test_removal_before_remove_after_is_rejected() -> None:
    errors = validate_removed_items(
        {"artifact:legacy": _deprecated(remove_after="2026-09-01")},
        {},
        LIFECYCLE,
        as_of=date(2026, 8, 16),
    )

    assert errors == [
        "error: artifact:legacy: removal is not permitted before remove_after=2026-09-01"
    ]


def test_removal_after_window_is_allowed() -> None:
    errors = validate_removed_items(
        {"skill:legacy-skill": _deprecated(remove_after="2026-04-01")},
        {},
        LIFECYCLE,
        as_of=date(2026, 8, 16),
    )

    assert errors == []


def test_same_identity_retained_does_not_require_deprecation() -> None:
    item = {"id": "route.current"}
    errors = validate_removed_items(
        {"stable:route.current": item},
        {"stable:route.current": item},
        LIFECYCLE,
        as_of=date(2026, 8, 16),
    )

    assert errors == []
