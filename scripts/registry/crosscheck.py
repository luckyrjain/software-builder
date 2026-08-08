from __future__ import annotations

from pathlib import Path

from scripts.registry.frontmatter import load_skill_frontmatter
from scripts.registry.schema import parse_registry


def _detect_cycles(skills: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str, stack: list[str]) -> None:
        if node in visiting:
            errors.append(
                f"error: install graph: cycle detected: {' -> '.join(stack + [node])}",
            )
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in skills.get(node, []):
            dfs(dep, stack + [node])
        visiting.remove(node)
        visited.add(node)

    for skill_id in skills:
        dfs(skill_id, [])
    return errors


def _skill_directories(root: Path) -> set[str]:
    return {
        path.parent.name
        for path in root.glob("*/SKILL.md")
        if path.parent.is_dir() and not path.parent.name.startswith(".")
    }


def validate_registry(root: Path) -> list[str]:
    errors: list[str] = []
    registry_path = root / "skills.yaml"
    registry = parse_registry(registry_path)

    skill_dirs = _skill_directories(root)
    registry_ids = set(registry.skills.keys())

    for orphan in sorted(skill_dirs - registry_ids):
        errors.append(f"error: {orphan}: directory has SKILL.md but no registry entry")
    for missing in sorted(registry_ids - skill_dirs):
        errors.append(f"error: {missing}: registry entry has no SKILL.md directory")

    install_graph: dict[str, list[str]] = {}
    for skill_id, entry in registry.skills.items():
        install_graph[skill_id] = list(entry.install.requires)
        for dep in entry.install.requires:
            if dep not in registry.skills:
                errors.append(f"error: {skill_id}: install.requires unknown skill {dep!r}")

    errors.extend(_detect_cycles(install_graph))

    for skill_id, entry in registry.skills.items():
        skill_md = root / entry.path / "SKILL.md"
        try:
            frontmatter = load_skill_frontmatter(skill_md)
        except ValueError as exc:
            errors.append(f"error: {skill_id}: {exc}")
            continue

        frontmatter_name = str(frontmatter.get("name", ""))
        if frontmatter_name != skill_id:
            errors.append(
                f"error: {skill_id}: name mismatch (SKILL.md name={frontmatter_name!r})",
            )
        if "description" not in frontmatter:
            errors.append(f"error: {skill_id}: SKILL.md missing description")

        disable = frontmatter.get("disable-model-invocation") is True
        automation_only = entry.invocation == "automation-only"
        if disable != automation_only:
            errors.append(
                f"error: {skill_id}: disable-model-invocation={disable} "
                f"but invocation={entry.invocation!r}",
            )

    return errors
