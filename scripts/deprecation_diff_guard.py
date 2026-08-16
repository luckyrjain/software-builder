#!/usr/bin/env python3
"""Block removal of governed prompt-system identities before deprecation matures."""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.deprecation_lifecycle import validate_deprecation_item


def _git_text(root: Path, ref: str, path: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "show", f"{ref}:{path}"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return None


def _mapping(text: str | None) -> dict[str, Any]:
    if text is None:
        return {}
    value = yaml.safe_load(text)
    return value if isinstance(value, dict) else {}


def _frontmatter(text: str | None) -> dict[str, Any]:
    if not text or not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    value = yaml.safe_load(text[4:end])
    return value if isinstance(value, dict) else {}


def governed_items(root: Path, ref: str) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Return durable identities plus the revision's lifecycle configuration."""
    upkeep = _mapping(_git_text(root, ref, "scripts/operational_upkeep.yaml"))
    items: dict[str, dict[str, Any]] = {}

    skills_file = _mapping(_git_text(root, ref, "skills.yaml"))
    skills = skills_file.get("skills", {})
    if isinstance(skills, dict):
        for skill_id, entry in skills.items():
            if not isinstance(entry, dict):
                continue
            skill_path = str(entry.get("path", skill_id))
            metadata = _frontmatter(_git_text(root, ref, f"{skill_path}/SKILL.md"))
            items[f"skill:{skill_id}"] = metadata

    composition = _mapping(_git_text(root, ref, "scripts/registry/composition_contracts.yaml"))
    schemas = composition.get("artifact_schemas", {})
    if isinstance(schemas, dict):
        for schema_id, spec in schemas.items():
            items[f"artifact:{schema_id}"] = spec if isinstance(spec, dict) else {}

    stable = upkeep.get("stable_ids", {})
    if isinstance(stable, dict):
        for group in ("routes", "stop_conditions", "report_fields"):
            entries = stable.get(group, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, dict) and entry.get("id"):
                    items[f"stable:{entry['id']}"] = entry

    lifecycle = upkeep.get("deprecation", {})
    return items, lifecycle if isinstance(lifecycle, dict) else {}


def validate_removed_items(
    base_items: dict[str, dict[str, Any]],
    head_items: dict[str, dict[str, Any]],
    lifecycle: dict[str, Any],
    *,
    as_of: date,
) -> list[str]:
    required = set(lifecycle.get("required_fields", []))
    window = lifecycle.get("compatibility_window_days")
    if not required or not isinstance(window, int) or window <= 0:
        return ["error: deprecation removal guard requires valid lifecycle configuration in the base revision"]

    errors: list[str] = []
    for identity in sorted(set(base_items) - set(head_items)):
        metadata = base_items[identity]
        if metadata.get("status") != "deprecated" and metadata.get("deprecated") is not True:
            errors.append(
                f"error: {identity}: removal requires deprecation in the base revision before deletion"
            )
            continue

        item_errors = validate_deprecation_item(
            metadata,
            identity,
            required_fields=required,
            compatibility_window_days=window,
        )
        if item_errors:
            errors.extend(item_errors)
            continue

        remove_after = date.fromisoformat(str(metadata["deprecation"]["remove_after"]))
        if as_of < remove_after:
            errors.append(
                f"error: {identity}: removal is not permitted before remove_after={remove_after.isoformat()}"
            )
    return errors


def validate_revision_removals(
    root: Path,
    base: str,
    head: str,
    *,
    as_of: date | None = None,
) -> list[str]:
    base_items, lifecycle = governed_items(root, base)
    head_items, _ = governed_items(root, head)
    return validate_removed_items(
        base_items,
        head_items,
        lifecycle,
        as_of=as_of or date.today(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args(argv)

    errors = validate_revision_removals(ROOT, args.base, args.head)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("ok: governed removals respect deprecation lifecycle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
