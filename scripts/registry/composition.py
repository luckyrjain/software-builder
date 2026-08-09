from __future__ import annotations

from pathlib import Path

from scripts.registry.composition_contracts import validate_composition_contracts
from scripts.registry.models import Registry
from scripts.registry.schema import parse_registry


def _detect_cycles(skills: dict[str, list[str]], label: str) -> list[str]:
    errors: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str, stack: list[str]) -> None:
        if node in visiting:
            errors.append(
                f"error: {label}: cycle detected: {' -> '.join(stack + [node])}",
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


def validate_composition_graph(registry: Registry) -> list[str]:
    errors: list[str] = []
    invokes_graph: dict[str, list[str]] = {}
    all_skill_ids = set(registry.skills.keys())

    for skill_id, entry in registry.skills.items():
        invokes_graph[skill_id] = list(entry.composition.invokes)
        for target in entry.composition.invokes:
            if target not in all_skill_ids:
                errors.append(
                    f"error: {skill_id}: composition.invokes unknown skill {target!r}",
                )
        for target in entry.composition.escalation_targets:
            if target not in all_skill_ids:
                errors.append(
                    f"error: {skill_id}: composition.escalation_targets unknown skill {target!r}",
                )
        if entry.composition.mode == "aggregate" and entry.composition.invokes:
            errors.append(
                f"error: {skill_id}: aggregate composition must not list runtime invokes",
            )

    errors.extend(_detect_cycles(invokes_graph, "composition graph"))
    errors.extend(validate_composition_contracts(registry))
    return errors


def render_composition_mermaid(registry: Registry) -> str:
    lines = ["graph TD"]
    edges = 0
    for skill_id, entry in sorted(registry.skills.items()):
        for dep in entry.composition.invokes:
            lines.append(f"  {skill_id} -->|invokes| {dep}")
            edges += 1
        for target in entry.composition.escalation_targets:
            lines.append(f"  {skill_id} -.->|escalates| {target}")
            edges += 1
    if edges == 0:
        lines.append("  empty[No composition edges]")
    return "\n".join(lines) + "\n"


def validate_composition_file(root: Path) -> list[str]:
    registry = parse_registry(root / "skills.yaml")
    return validate_composition_graph(registry)
