"""Backfill skills.yaml capabilities blocks from capability_catalog.yaml."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = Path(__file__).resolve().parent / "capability_catalog.yaml"
SKILLS_PATH = ROOT / "skills.yaml"


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, dict[str, Any]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be a mapping")
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        raise ValueError(f"{path}: skills must be a mapping")
    return {str(skill_id): dict(entry) for skill_id, entry in skills.items()}


def _capabilities_valid(entry: dict[str, Any]) -> bool:
    caps = entry.get("capabilities")
    if not isinstance(caps, dict):
        return False
    required = caps.get("required")
    optional = caps.get("optional")
    if not isinstance(required, list) or not isinstance(optional, list):
        return False
    return bool(required or optional)


def _format_capabilities_block(capabilities: dict[str, Any]) -> list[str]:
    dumped = yaml.safe_dump(
        {"capabilities": capabilities},
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    ).rstrip().splitlines()
    return ["    " + line if line.strip() else "" for line in dumped]


def _block_has_stray_capability_keys(block_lines: list[str]) -> bool:
    in_capabilities = False
    for line in block_lines:
        if line.startswith("    capabilities:"):
            in_capabilities = True
            continue
        if in_capabilities:
            if line.startswith("    ") and not line.startswith("      "):
                in_capabilities = False
            else:
                continue
        if (
            line.startswith("    required:")
            or line.startswith("    optional:")
            or line.startswith("    degraded_modes:")
        ):
            return True
    return False


def _strip_capabilities_block(block_lines: list[str]) -> list[str]:
    cleaned: list[str] = []
    index = 0
    while index < len(block_lines):
        line = block_lines[index]
        if line.startswith("    capabilities:"):
            index += 1
            while index < len(block_lines) and (
                block_lines[index].startswith("      ") or block_lines[index].strip() == ""
            ):
                index += 1
            continue
        if line.startswith("    required:") or line.startswith("    optional:"):
            index += 1
            while index < len(block_lines) and (
                block_lines[index].startswith("    -")
                or block_lines[index].startswith("      ")
                or block_lines[index].strip() == ""
            ):
                index += 1
            continue
        if line.startswith("    degraded_modes:"):
            index += 1
            while index < len(block_lines) and (
                block_lines[index].startswith("      ") or block_lines[index].strip() == ""
            ):
                index += 1
            continue
        cleaned.append(line)
        index += 1
    return cleaned


def _skill_block_bounds(lines: list[str], skill_id: str) -> tuple[int, int]:
    header = f"  {skill_id}:"
    start = None
    for index, line in enumerate(lines):
        if line == header:
            start = index
            break
    if start is None:
        raise ValueError(f"skills.yaml missing skill block: {skill_id}")

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r"^  [a-z0-9-]+:$", lines[index]):
            end = index
            break
    return start, end


def _insert_before_lint(block_lines: list[str], cap_lines: list[str]) -> list[str]:
    for index, line in enumerate(block_lines):
        if line.startswith("    lint:"):
            return block_lines[:index] + cap_lines + [""] + block_lines[index:]
    raise ValueError("skill block missing lint section")


def backfill_skills_yaml_text(
    text: str,
    *,
    catalog_path: Path = CATALOG_PATH,
    overwrite: bool = False,
) -> tuple[str, list[str]]:
    catalog = load_catalog(catalog_path)
    raw = yaml.safe_load(text)
    if not isinstance(raw, dict):
        raise ValueError("skills.yaml root must be a mapping")
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        raise ValueError("skills.yaml skills must be a mapping")

    registry_ids = set(skills.keys())
    catalog_ids = set(catalog.keys())
    missing_in_catalog = sorted(registry_ids - catalog_ids)
    if missing_in_catalog:
        raise ValueError(
            f"capability catalog missing entries for: {', '.join(missing_in_catalog)}",
        )
    extra_in_catalog = sorted(catalog_ids - registry_ids)
    if extra_in_catalog:
        raise ValueError(
            f"capability catalog has unknown skill ids: {', '.join(extra_in_catalog)}",
        )

    lines = text.splitlines()
    changes: list[str] = []

    for skill_id in sorted(skills):
        entry = skills[skill_id]
        if not isinstance(entry, dict):
            raise ValueError(f"skills.{skill_id} must be a mapping")
        start, end = _skill_block_bounds(lines, skill_id)
        block = lines[start:end]
        if _capabilities_valid(entry) and not _block_has_stray_capability_keys(block):
            continue

        block = _strip_capabilities_block(block)
        cap_lines = _format_capabilities_block(catalog[skill_id])
        new_block = _insert_before_lint(block, cap_lines)
        lines = lines[:start] + new_block + lines[end:]
        changes.append(skill_id)

    return "\n".join(lines) + ("\n" if text.endswith("\n") else ""), changes


def validate_capabilities_present(skills_path: Path = SKILLS_PATH) -> list[str]:
    from scripts.registry.schema import parse_registry

    raw = yaml.safe_load(skills_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return ["error: skills.yaml root must be a mapping"]
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        return ["error: skills.yaml skills must be a mapping"]

    errors: list[str] = []
    for skill_id, entry in skills.items():
        if not isinstance(entry, dict):
            errors.append(f"error: {skill_id}: skill entry must be a mapping")
            continue
        for orphan_key in ("required", "optional", "degraded_modes"):
            if orphan_key in entry:
                errors.append(
                    f"error: {skill_id}: stray top-level {orphan_key!r} key (belongs under capabilities)",
                )
        capabilities = entry.get("capabilities")
        if not isinstance(capabilities, dict):
            errors.append(f"error: {skill_id}: missing capabilities block")
            continue
        required = capabilities.get("required", [])
        optional = capabilities.get("optional", [])
        if not isinstance(required, list):
            errors.append(f"error: {skill_id}: capabilities.required must be a list")
        if not isinstance(optional, list):
            errors.append(f"error: {skill_id}: capabilities.optional must be a list")

    registry = parse_registry(skills_path)
    for skill_id, entry in registry.skills.items():
        caps = entry.capabilities
        if not caps.required and not caps.optional:
            errors.append(f"error: {skill_id}: capabilities block is empty after parse")
    return errors


def cmd_backfill(*, check_only: bool, overwrite: bool, skills_path: Path) -> int:
    try:
        original = skills_path.read_text(encoding="utf-8")
        updated, changes = backfill_skills_yaml_text(original, overwrite=overwrite)
    except (ValueError, yaml.YAMLError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not changes:
        print("ok: all skills already have capabilities blocks")
        return 0

    if check_only:
        print(
            f"error: {len(changes)} skill(s) missing capabilities: {', '.join(changes)}",
            file=sys.stderr,
        )
        print("hint: run python3 -m scripts.registry backfill-capabilities", file=sys.stderr)
        return 1

    skills_path.write_text(updated, encoding="utf-8")
    print(f"ok: backfilled capabilities for {len(changes)} skill(s): {', '.join(changes)}")
    return 0
