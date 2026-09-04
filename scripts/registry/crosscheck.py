from __future__ import annotations

import re
from pathlib import Path

from scripts.registry.backfill_capabilities import validate_capabilities_present
from scripts.registry.composition import validate_composition_graph
from scripts.registry.escalation_sync import validate_escalation_matrix
from scripts.registry.canonical_manifest import has_canonical_manifest_shape
from scripts.registry.graph import detect_cycles
from scripts.registry.load import load_deprecated_skills
from scripts.registry.models import Registry
from scripts.registry.routing_sync import (
    validate_skill_not_these_subsets,
    validate_skill_routing_references,
)
from scripts.registry.schema import AUTOMATION_ONLY_INVOCATION, load_registry_raw, parse_registry
from scripts.registry.skill_contract_adoption_sync import validate_skill_contract_adoption
from scripts.registry.skill_frontmatter_schema import (
    automation_only_guard_errors,
    validate_skill_frontmatter_fields,
)
from scripts.yaml_safety import YAML_SAFETY_ERRORS, load_unique_frontmatter

_SKILL_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_GENERATED_MARKER = "GENERATED from skills.yaml"


def _skill_directories(root: Path) -> set[str]:
    return {
        path.parent.name
        for path in root.glob("*/SKILL.md")
        if path.parent.is_dir() and not path.parent.name.startswith(".")
    }


def _validate_skill_path(root: Path, skill_id: str, entry_path: str) -> list[str]:
    errors: list[str] = []
    if not _SKILL_ID_RE.match(skill_id):
        errors.append(f"error: {skill_id}: skill id must be lowercase kebab-case (no leading/trailing/double hyphens)")
    if entry_path != skill_id:
        errors.append(
            f"error: {skill_id}: path {entry_path!r} must match skill id (no aliases in v1)",
        )
    resolved_skill_md = (root / entry_path / "SKILL.md").resolve()
    root_resolved = root.resolve()
    try:
        resolved_skill_md.relative_to(root_resolved)
    except ValueError:
        errors.append(f"error: {skill_id}: path escapes repository root")
    return errors


def _adapter_active_skill_ids(root: Path, registry: Registry) -> set[str]:
    """Registered skill ids that should still have generated Cursor/Kiro adapters.

    A skill marked deprecated (docs/skill-framework/shared/deprecation-policy.md) stays
    registered through its compatibility window, but loses its ambient-invocation surface
    immediately -- generate_cursor.py/generate_kiro.py stop (re)emitting its adapter, and
    this treats it the same as an unregistered skill so any copy already on disk gets
    pruned. Reuses load_deprecated_skills's own tolerant frontmatter handling (a skill
    whose SKILL.md can't be read or parsed is kept active, not pruned) rather than
    re-walking the registry with separate, easily-inconsistent error handling -- that
    mismatch is `validate`'s job to report, not this one's.
    """
    deprecated = load_deprecated_skills(root, registry)
    return set(registry.skills) - set(deprecated)


def find_stale_generated_adapters(root: Path, registry: Registry) -> list[Path]:
    """Return generated adapter files whose skill id is no longer in the registry, or
    that belongs to a skill now marked deprecated (see _adapter_active_skill_ids)."""
    active = _adapter_active_skill_ids(root, registry)
    stale: list[Path] = []
    for pattern in (".cursor/rules/*.mdc", ".kiro/steering/*.md"):
        for path in sorted(root.glob(pattern)):
            if path.stem in active:
                continue
            try:
                if _GENERATED_MARKER in path.read_text(encoding="utf-8"):
                    stale.append(path)
            except OSError:
                continue
    return stale


def _validate_skill_directory_sync(root: Path, registry: Registry) -> list[str]:
    """Every SKILL.md directory must have a registry entry and vice versa."""
    errors: list[str] = []
    skill_dirs = _skill_directories(root)
    registry_ids = set(registry.skills.keys())
    for orphan in sorted(skill_dirs - registry_ids):
        errors.append(f"error: {orphan}: directory has SKILL.md but no registry entry")
    for missing in sorted(registry_ids - skill_dirs):
        errors.append(f"error: {missing}: registry entry has no SKILL.md directory")
    return errors


def _validate_skill_paths(root: Path, registry: Registry) -> list[str]:
    errors: list[str] = []
    for skill_id, entry in registry.skills.items():
        errors.extend(_validate_skill_path(root, skill_id, entry.path))
    return errors


def _validate_install_graph(registry: Registry) -> list[str]:
    """install.requires must reference known skills and form no dependency cycle."""
    errors: list[str] = []
    install_graph: dict[str, list[str]] = {}
    for skill_id, entry in registry.skills.items():
        install_graph[skill_id] = list(entry.install.requires)
        for dep in entry.install.requires:
            if dep not in registry.skills:
                errors.append(f"error: {skill_id}: install.requires unknown skill {dep!r}")
    errors.extend(detect_cycles(install_graph, "install graph"))
    return errors


def _invoke_capability_names(entry: object) -> list[str]:
    capabilities = getattr(entry, "capabilities")
    names = [item.name for item in capabilities.optional]
    for path in capabilities.any_of:
        names.extend(item.name for item in path.optional)
        names.extend(path.required)
    names.extend(capabilities.required)
    return [name for name in names if name.endswith(".invoke")]


def _validate_invoke_skill_references(registry: Registry) -> list[str]:
    """Machine-readable skill invocation references must resolve and be installable."""
    errors: list[str] = []
    known = set(registry.skills)
    for skill_id, entry in registry.skills.items():
        dependencies = set(entry.install.requires)
        for capability in _invoke_capability_names(entry):
            target = capability[: -len(".invoke")]
            if target not in known:
                errors.append(f"error: {skill_id}: capability references unknown skill {target!r}")
            elif target not in dependencies:
                errors.append(
                    f"error: {skill_id}: capability {capability!r} requires install.requires {target!r}",
                )
    return errors


def _validate_skill_frontmatter_shape(root: Path, registry: Registry) -> list[str]:
    """Per-skill SKILL.md frontmatter checks against the registry."""
    errors: list[str] = []
    raw_manifest = load_registry_raw(root / "skills.yaml")
    legacy_manifest = not has_canonical_manifest_shape(raw_manifest)
    for skill_id, entry in registry.skills.items():
        skill_md = root / entry.path / "SKILL.md"
        try:
            frontmatter = load_unique_frontmatter(skill_md)
        except YAML_SAFETY_ERRORS as exc:
            errors.append(f"error: {skill_id}: {exc}")
            continue

        frontmatter_name = str(frontmatter.get("name", ""))
        if frontmatter_name != skill_id:
            errors.append(
                f"error: {skill_id}: name mismatch (SKILL.md name={frontmatter_name!r})",
            )
        if "description" not in frontmatter:
            errors.append(f"error: {skill_id}: SKILL.md missing description")
        else:
            description = frontmatter.get("description", "")
            if not isinstance(description, str) or not description.strip():
                errors.append(f"error: {skill_id}: description must be a non-empty string")
            elif "Keywords:" not in description:
                # Every skill's ambient-routing surface is its frontmatter description — the
                # thing a host actually reads to decide whether to invoke it. "Keywords: ..." is
                # this repo's convention for making that surface greppable/consistent; skipping it
                # is how 4 skills quietly drifted from the other 34 before this check existed.
                errors.append(
                    f"error: {skill_id}: description missing 'Keywords:' — every other skill's "
                    f"SKILL.md frontmatter description states its routing keywords as "
                    f"'Keywords: term, term, ...' (see e.g. pr-review/SKILL.md); add the same here",
                )

        errors.extend(
            validate_skill_frontmatter_fields(
                skill_id,
                frontmatter,
                require_legacy_platform_fields=legacy_manifest,
            )
        )
        errors.extend(
            f"error: {skill_id}: {msg}"
            for msg in automation_only_guard_errors(entry.invocation, frontmatter)
        )
    return errors


def _validate_automation_only_rules(registry: Registry) -> list[str]:
    errors: list[str] = []
    for skill_id, entry in registry.skills.items():
        if entry.invocation != AUTOMATION_ONLY_INVOCATION:
            continue
        cursor_host = entry.hosts.get("cursor")
        if cursor_host is not None and cursor_host.discovery == "always":
            errors.append(
                f"error: {skill_id}: automation-only skills cannot use cursor discovery always",
            )
        kiro_host = entry.hosts.get("kiro")
        if kiro_host is not None and kiro_host.discovery == "always":
            errors.append(
                f"error: {skill_id}: automation-only skills cannot use kiro discovery always",
            )
        if "unattended" not in entry.risk_class:
            errors.append(
                f"error: {skill_id}: automation-only skills must declare risk_class unattended",
            )
    return errors


def _validate_stale_adapters(root: Path, registry: Registry) -> list[str]:
    return [
        f"error: stale generated adapter: {path.relative_to(root)}"
        for path in find_stale_generated_adapters(root, registry)
    ]


def validate_registry(root: Path) -> list[str]:
    registry_path = root / "skills.yaml"
    registry = parse_registry(registry_path)

    errors: list[str] = []
    errors.extend(_validate_skill_directory_sync(root, registry))
    errors.extend(_validate_skill_paths(root, registry))
    errors.extend(_validate_install_graph(registry))
    errors.extend(_validate_invoke_skill_references(registry))
    errors.extend(validate_composition_graph(registry))
    errors.extend(validate_capabilities_present(registry_path))
    errors.extend(_validate_skill_frontmatter_shape(root, registry))
    errors.extend(_validate_automation_only_rules(registry))
    errors.extend(_validate_stale_adapters(root, registry))
    errors.extend(validate_skill_routing_references(root, registry))
    errors.extend(validate_skill_not_these_subsets(root, registry))
    errors.extend(validate_escalation_matrix(root, registry))
    errors.extend(validate_skill_contract_adoption(root, registry))
    return errors
