from __future__ import annotations


def detect_cycles(skills: dict[str, list[str]], label: str) -> list[str]:
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
