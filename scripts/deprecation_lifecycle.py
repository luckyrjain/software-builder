#!/usr/bin/env python3
"""Validate deprecated prompt/contract items against the configured lifecycle window."""

from __future__ import annotations

import re
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from scripts.operational_upkeep import (
    _deprecation_candidates,
    _registered_skills,
    _validate_deprecation_mapping,
    load_policy,
)

ROOT = Path(__file__).resolve().parents[1]
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_deprecation_item(
    data: dict[str, Any],
    label: str,
    *,
    required_fields: set[str],
    compatibility_window_days: int,
) -> list[str]:
    base_errors = _validate_deprecation_mapping(data, label, required_fields)
    if data.get("status") != "deprecated" and data.get("deprecated") is not True:
        return base_errors
    if base_errors:
        return base_errors

    block = data["deprecation"]
    errors: list[str] = []
    parsed: dict[str, date] = {}
    for field in ("deprecated_since", "remove_after"):
        raw = block.get(field)
        try:
            # PyYAML's SafeLoader auto-parses an unquoted YYYY-MM-DD scalar into
            # a datetime.date, not a str; accept both spellings. Reject
            # datetime.datetime (a date subclass) explicitly -- comparing a
            # naive datetime to a plain date raises TypeError below.
            if type(raw) is date:
                parsed[field] = raw
            elif isinstance(raw, str) and _DATE_RE.fullmatch(raw):
                parsed[field] = date.fromisoformat(raw)
            else:
                raise ValueError
        except ValueError:
            errors.append(f"error: {label}: deprecation {field} must be an ISO date (YYYY-MM-DD)")

    if len(parsed) == 2:
        earliest = parsed["deprecated_since"] + timedelta(days=compatibility_window_days)
        if parsed["remove_after"] < earliest:
            errors.append(
                f"error: {label}: remove_after must be at least {compatibility_window_days} days after deprecated_since"
            )
    return errors


def validate_repository(root: Path = ROOT) -> list[str]:
    policy = load_policy(root / "scripts" / "operational_upkeep.yaml")
    lifecycle = policy.get("deprecation", {})
    required = set(lifecycle.get("required_fields", [])) if isinstance(lifecycle, dict) else set()
    window = lifecycle.get("compatibility_window_days") if isinstance(lifecycle, dict) else None
    errors: list[str] = []
    if not required:
        errors.append("error: deprecation lifecycle required_fields must not be empty")
    if not isinstance(window, int) or window <= 0:
        errors.append("error: deprecation compatibility_window_days must be a positive integer")
        return errors

    skills = _registered_skills(root)
    skill_paths = [
        str(entry.get("path", skill_id))
        for skill_id, entry in skills.items()
        if isinstance(entry, dict)
    ]
    for label, data in _deprecation_candidates(root, skill_paths):
        errors.extend(
            validate_deprecation_item(
                data,
                label,
                required_fields=required,
                compatibility_window_days=window,
            )
        )
    return errors


def main() -> int:
    errors = validate_repository()
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("ok: deprecation lifecycle validates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
