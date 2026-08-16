#!/usr/bin/env python3
"""Validate deprecated prompt/contract items against the configured lifecycle window."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    data = yaml.safe_load(text[4:end])
    return data if isinstance(data, dict) else {}


def _nested(value: Any, label: str) -> Iterator[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        yield label, value
        for key, child in value.items():
            yield from _nested(child, f"{label}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _nested(child, f"{label}[{index}]")


def _candidates(root: Path) -> Iterable[tuple[str, dict[str, Any]]]:
    for path in sorted((root / "scripts" / "registry").glob("*.yaml")):
        yield from _nested(_mapping(path), path.relative_to(root).as_posix())

    skills = _mapping(root / "skills.yaml").get("skills", {})
    if not isinstance(skills, dict):
        return
    for skill_id, entry in skills.items():
        if not isinstance(entry, dict):
            continue
        skill_path = root / str(entry.get("path", skill_id))
        skill_md = skill_path / "SKILL.md"
        if skill_md.is_file():
            yield from _nested(_frontmatter(skill_md), skill_md.relative_to(root).as_posix())
        for pattern in ("reference/*.yaml", "reference/*.yml", "templates/*.yaml", "templates/*.yml"):
            for path in sorted(skill_path.glob(pattern)):
                yield from _nested(_mapping(path), path.relative_to(root).as_posix())


def validate_deprecation_item(
    data: dict[str, Any],
    label: str,
    *,
    required_fields: set[str],
    compatibility_window_days: int,
) -> list[str]:
    if data.get("status") != "deprecated" and data.get("deprecated") is not True:
        return []
    block = data.get("deprecation")
    if not isinstance(block, dict):
        return [f"error: {label}: deprecated item requires a deprecation mapping"]

    missing = sorted(required_fields - set(block))
    if missing:
        return [f"error: {label}: deprecation missing fields: {', '.join(missing)}"]

    errors: list[str] = []
    for field in required_fields - {"aliases"}:
        value = block.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors.append(f"error: {label}: deprecation field {field} must be non-empty")
    if not isinstance(block.get("aliases"), list):
        errors.append(f"error: {label}: deprecation aliases must be a list")

    parsed: dict[str, date] = {}
    for field in ("deprecated_since", "remove_after"):
        raw = block.get(field)
        try:
            if not isinstance(raw, str):
                raise ValueError
            parsed[field] = date.fromisoformat(raw)
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
    policy = _mapping(root / "scripts" / "operational_upkeep.yaml")
    lifecycle = policy.get("deprecation", {})
    required = set(lifecycle.get("required_fields", [])) if isinstance(lifecycle, dict) else set()
    window = lifecycle.get("compatibility_window_days") if isinstance(lifecycle, dict) else None
    errors: list[str] = []
    if not required:
        errors.append("error: deprecation lifecycle required_fields must not be empty")
    if not isinstance(window, int) or window <= 0:
        errors.append("error: deprecation compatibility_window_days must be a positive integer")
        return errors
    for label, data in _candidates(root):
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
