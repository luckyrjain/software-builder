#!/usr/bin/env python3
"""Validate (and optionally backfill) SETUP.md freshness tables per setup_freshness.yaml."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

_FRESHNESS_HEADING = "## Freshness"
_LAST_REVIEWED_RE = re.compile(
    r"\*\*Last reviewed\*\*\s*\|\s*(\d{4}-\d{2}-\d{2})",
)
_EXTERNAL_RE = re.compile(r"\*\*External services\*\*\s*\|\s*(.+?)\s*\|")


def _load_config(root: Path) -> tuple[dict, dict]:
    path = root / "scripts/registry/setup_freshness.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    defaults = raw.get("defaults") or {}
    skills = raw.get("skills") or {}
    if not isinstance(skills, dict):
        raise ValueError("setup_freshness.yaml skills must be a mapping")
    return defaults, skills


def _render_freshness_block(
    *,
    owner: str,
    last_reviewed: str,
    review_cadence: str,
    external_services: str,
) -> str:
    return (
        f"{_FRESHNESS_HEADING}\n\n"
        "| Field | Value |\n"
        "|-------|-------|\n"
        f"| **Owner** | {owner} |\n"
        f"| **Last reviewed** | {last_reviewed} |\n"
        f"| **Review cadence** | {review_cadence} |\n"
        f"| **External services** | {external_services} |\n\n"
        "See [setup-freshness.md](../docs/skill-framework/shared/setup-freshness.md) "
        "for the shared contract.\n"
    )


def _insert_after_title(text: str, block: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines:
        return block
    # Title is first line (# ...); insert block after title + optional blank line
    insert_at = 1
    if len(lines) > 1 and lines[1].strip() == "":
        insert_at = 2
    return "".join(lines[:insert_at]) + "\n" + block + "".join(lines[insert_at:])


def ensure_setup_freshness(root: Path, *, write: bool) -> list[str]:
    defaults, skills_cfg = _load_config(root)
    owner = str(defaults.get("owner", "software-builder maintainers"))
    review_cadence = str(
        defaults.get("review_cadence", "Quarterly — or when pinned MCP package versions change"),
    )
    last_reviewed = str(defaults.get("last_reviewed", date.today().isoformat()))
    max_age_days = int(defaults.get("max_age_days", 120))

    errors: list[str] = []
    for skill_id, cfg in sorted(skills_cfg.items()):
        if not isinstance(cfg, dict):
            errors.append(f"error: setup_freshness skills.{skill_id} must be a mapping")
            continue
        setup_path = root / skill_id / "SETUP.md"
        if not setup_path.is_file():
            errors.append(f"error: {skill_id}: missing SETUP.md")
            continue

        external = str(cfg.get("external_services", "None"))
        block = _render_freshness_block(
            owner=owner,
            last_reviewed=last_reviewed,
            review_cadence=review_cadence,
            external_services=external,
        )

        text = setup_path.read_text(encoding="utf-8")
        if _FRESHNESS_HEADING not in text:
            if write:
                setup_path.write_text(_insert_after_title(text, block), encoding="utf-8")
                continue
            errors.append(f"error: {skill_id}/SETUP.md missing {_FRESHNESS_HEADING} section")
            continue

        reviewed_match = _LAST_REVIEWED_RE.search(text)
        if not reviewed_match:
            errors.append(f"error: {skill_id}/SETUP.md missing **Last reviewed** date")
            continue
        reviewed = datetime.strptime(reviewed_match.group(1), "%Y-%m-%d").date()
        if date.today() - reviewed > timedelta(days=max_age_days):
            errors.append(
                f"error: {skill_id}/SETUP.md Last reviewed {reviewed} exceeds {max_age_days}d cadence",
            )

        external_match = _EXTERNAL_RE.search(text)
        if not external_match:
            errors.append(f"error: {skill_id}/SETUP.md missing **External services** row")
            continue
        actual_external = external_match.group(1).strip()
        if actual_external != external:
            errors.append(
                f"error: {skill_id}/SETUP.md External services mismatch "
                f"(expected {external!r}, got {actual_external!r})",
            )

        if "setup-freshness.md" not in text:
            errors.append(f"error: {skill_id}/SETUP.md must link to setup-freshness.md")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Insert missing Freshness sections (does not overwrite existing tables)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    args = parser.parse_args(argv)

    errors = ensure_setup_freshness(args.root, write=args.write)
    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1
    print(f"ok — SETUP.md freshness validated for {args.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
