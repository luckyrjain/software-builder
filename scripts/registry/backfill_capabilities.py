"""Backfill skills.yaml capabilities blocks from capability_catalog.yaml."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import yaml
from ruamel.yaml import YAML
from ruamel.yaml import YAMLError as RuamelYAMLError
from ruamel.yaml.comments import CommentedMap

ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = Path(__file__).resolve().parent / "capability_catalog.yaml"
SKILLS_PATH = ROOT / "skills.yaml"

# skills.yaml's own convention: sequence dashes sit at the same indent as their
# parent key (37 of 41 existing required/optional blocks use this; the minority
# get normalized to it on first write — see backfill_skills_yaml_text).
_STRAY_CAPABILITY_KEYS = ("required", "optional", "degraded_modes")


def _make_yaml() -> YAML:
    rt_yaml = YAML(typ="rt")
    rt_yaml.preserve_quotes = True
    rt_yaml.width = 100000
    rt_yaml.indent(mapping=2, sequence=2, offset=0)
    return rt_yaml


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, Any]:
    # Loaded via the round-trip YAML so a catalog entry's own style choices
    # (e.g. `required: [a, b]` written as flow style) survive into skills.yaml
    # when a block is (re)generated, instead of being flattened to block style.
    raw = _make_yaml().load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: root must be a mapping")
    skills = raw.get("skills")
    if not isinstance(skills, dict):
        raise ValueError(f"{path}: skills must be a mapping")
    return {str(skill_id): entry for skill_id, entry in skills.items()}


def _capabilities_valid(entry: dict[str, Any]) -> bool:
    caps = entry.get("capabilities")
    if not isinstance(caps, dict):
        return False
    required = caps.get("required")
    optional = caps.get("optional")
    return isinstance(required, list) and isinstance(optional, list)


def _capabilities_equal(current: Any, catalog_value: dict[str, Any]) -> bool:
    if not isinstance(current, dict):
        return False
    if set(current.get("required") or []) != set(catalog_value.get("required") or []):
        return False
    current_optional = {item.get("name"): item for item in (current.get("optional") or [])}
    catalog_optional = {item.get("name"): item for item in (catalog_value.get("optional") or [])}
    if current_optional != catalog_optional:
        return False
    return (current.get("degraded_modes") or {}) == (catalog_value.get("degraded_modes") or {})


def _has_stray_capability_keys(entry: dict[str, Any]) -> bool:
    return any(key in entry for key in _STRAY_CAPABILITY_KEYS)


def _apply_backfill(skill_map: CommentedMap, capabilities: Any) -> None:
    for key in _STRAY_CAPABILITY_KEYS:
        skill_map.pop(key, None)
    skill_map.pop("capabilities", None)
    try:
        lint_index = list(skill_map.keys()).index("lint")
    except ValueError as exc:
        raise ValueError("skill block missing lint section") from exc
    skill_map.insert(lint_index, "capabilities", capabilities)
    # Matches this tool's existing convention: a freshly-generated capabilities
    # block is followed by a blank line before `lint:`. Clear any comment this
    # tool previously attached to `lint` first -- yaml_set_comment_before_after_key
    # appends rather than replaces, so re-backfilling the same skill without this
    # would double the blank line each time.
    skill_map.ca.items.pop("lint", None)
    skill_map.yaml_set_comment_before_after_key("lint", before="\n")


def backfill_skills_yaml_text(
    text: str,
    *,
    catalog_path: Path = CATALOG_PATH,
    overwrite: bool = False,
    render: bool = True,
) -> tuple[str, list[str]]:
    catalog = load_catalog(catalog_path)
    rt_yaml = _make_yaml()
    raw = rt_yaml.load(text)
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

    changes: list[str] = []
    for skill_id in sorted(skills):
        entry = skills[skill_id]
        if not isinstance(entry, dict):
            raise ValueError(f"skills.{skill_id} must be a mapping")

        stray = _has_stray_capability_keys(entry)
        if overwrite:
            if _capabilities_equal(entry.get("capabilities"), catalog[skill_id]) and not stray:
                continue
        elif _capabilities_valid(entry) and not stray:
            continue

        _apply_backfill(entry, catalog[skill_id])
        changes.append(skill_id)

    if not render:
        return "", changes

    # Dumps the whole document, not just the skill(s) in `changes` -- intentional:
    # any formatting drift elsewhere in skills.yaml self-heals on the next write
    # instead of accumulating. See the PR that introduced this for the tradeoff.
    buf = io.StringIO()
    rt_yaml.dump(raw, buf)
    updated = buf.getvalue()
    if text.endswith("\n") and not updated.endswith("\n"):
        updated += "\n"
    elif not text.endswith("\n") and updated.endswith("\n"):
        updated = updated[:-1]
    return updated, changes


def validate_capabilities_present(skills_path: Path = SKILLS_PATH) -> list[str]:
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
        for orphan_key in _STRAY_CAPABILITY_KEYS:
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

    return errors


def cmd_backfill(*, check_only: bool, overwrite: bool, skills_path: Path) -> int:
    try:
        original = skills_path.read_text(encoding="utf-8")
        updated, changes = backfill_skills_yaml_text(
            original, overwrite=overwrite, render=not check_only,
        )
    except (ValueError, yaml.YAMLError, RuamelYAMLError, RecursionError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if check_only:
        if changes:
            print(
                f"error: {len(changes)} skill(s) missing capabilities: {', '.join(changes)}",
                file=sys.stderr,
            )
            hint_flag = " --overwrite" if overwrite else ""
            print(
                f"hint: run python3 -m scripts.registry backfill-capabilities{hint_flag}",
                file=sys.stderr,
            )
            return 1
        print("ok: all skills already have capabilities blocks")
        return 0

    if updated == original:
        print("ok: all skills already have capabilities blocks")
        return 0

    skills_path.write_text(updated, encoding="utf-8")
    if changes:
        print(f"ok: backfilled capabilities for {len(changes)} skill(s): {', '.join(changes)}")
    else:
        print("ok: normalized skills.yaml formatting (no capability changes)")
    return 0
