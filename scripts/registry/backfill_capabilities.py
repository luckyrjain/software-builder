"""Backfill skills.yaml capabilities blocks from capability_catalog.yaml."""

from __future__ import annotations

import copy
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
_STRAY_CAPABILITY_KEYS = ("required", "optional", "any_of", "degraded_modes")


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
    for skill_id, entry in skills.items():
        if not isinstance(entry, dict):
            raise ValueError(f"{path}: skills.{skill_id} must be a mapping")
    return {str(skill_id): entry for skill_id, entry in skills.items()}


def _capabilities_valid(entry: dict[str, Any]) -> bool:
    caps = entry.get("capabilities")
    if not isinstance(caps, dict):
        return False
    required = caps.get("required")
    optional = caps.get("optional")
    any_of = caps.get("any_of", [])
    if not (
        isinstance(required, list)
        and isinstance(optional, list)
        and isinstance(any_of, list)
    ):
        return False
    return isinstance(caps.get("degraded_modes", {}), dict)


def _capabilities_equal(current: Any, catalog_value: dict[str, Any]) -> bool:
    # Never raises on malformed input (unhashable/non-string required items,
    # non-dict optional items) -- treats it as "not equal" so the skill gets
    # regenerated from the catalog instead of crashing the whole --overwrite run.
    if not isinstance(current, dict):
        return False

    current_required = current.get("required")
    catalog_required = catalog_value.get("required")
    if not (
        isinstance(current_required, list)
        and isinstance(catalog_required, list)
        and all(isinstance(item, str) for item in current_required)
        and all(isinstance(item, str) for item in catalog_required)
    ):
        return False
    if len(current_required) != len(set(current_required)):
        return False
    if set(current_required) != set(catalog_required):
        return False

    current_optional = current.get("optional")
    catalog_optional = catalog_value.get("optional")
    if not (isinstance(current_optional, list) and isinstance(catalog_optional, list)):
        return False
    if not all(
        isinstance(item, dict) and isinstance(item.get("name"), str)
        for item in (*current_optional, *catalog_optional)
    ):
        return False
    current_by_name = {item["name"]: item for item in current_optional}
    catalog_by_name = {item["name"]: item for item in catalog_optional}
    if len(current_by_name) != len(current_optional) or len(catalog_by_name) != len(catalog_optional):
        return False
    if current_by_name != catalog_by_name:
        return False

    current_any_of = current.get("any_of", [])
    catalog_any_of = catalog_value.get("any_of", [])
    if not (isinstance(current_any_of, list) and isinstance(catalog_any_of, list)):
        return False
    if not all(
        isinstance(item, dict) and isinstance(item.get("name"), str)
        for item in (*current_any_of, *catalog_any_of)
    ):
        return False
    current_paths = {item["name"]: item for item in current_any_of}
    catalog_paths = {item["name"]: item for item in catalog_any_of}
    if len(current_paths) != len(current_any_of) or len(catalog_paths) != len(catalog_any_of):
        return False
    if current_paths.keys() != catalog_paths.keys():
        return False
    if any(
        not _capabilities_equal(current_paths[name], catalog_paths[name])
        for name in current_paths
    ):
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
    # block is followed by a blank line before `lint:`. Clear only the "before"
    # comment slot (index 1) this tool may have attached on a prior backfill
    # first -- yaml_set_comment_before_after_key appends rather than replaces,
    # so skipping this would double the blank line on every re-backfill.
    # Only index 1 is touched so an unrelated same-line comment on `lint:`
    # (index 2) survives.
    lint_comments = skill_map.ca.items.get("lint")
    if lint_comments is not None:
        lint_comments[1] = None
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

        changes.append(skill_id)
        if render:
            # Deep-copied so two skills that ever share the same catalog
            # entry object (e.g. a future YAML anchor/alias in the catalog)
            # don't end up aliased to the same node in skills.yaml.
            _apply_backfill(entry, copy.deepcopy(catalog[skill_id]))

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
        any_of = capabilities.get("any_of", [])
        if not isinstance(required, list):
            errors.append(f"error: {skill_id}: capabilities.required must be a list")
        if not isinstance(optional, list):
            errors.append(f"error: {skill_id}: capabilities.optional must be a list")
        if not isinstance(any_of, list):
            errors.append(f"error: {skill_id}: capabilities.any_of must be a list")
        degraded_modes = capabilities.get("degraded_modes", {})
        if not isinstance(degraded_modes, dict):
            errors.append(f"error: {skill_id}: capabilities.degraded_modes must be a mapping")

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
            reason = "capabilities out of date with the catalog" if overwrite else "missing capabilities"
            print(
                f"error: {len(changes)} skill(s) {reason}: {', '.join(changes)}",
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
