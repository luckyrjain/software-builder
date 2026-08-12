from __future__ import annotations

from pathlib import Path

from scripts.registry.backfill_capabilities import load_catalog
from scripts.registry.composition_contracts import load_contracts
from scripts.registry.load import load_registry
from scripts.release_info import read_distribution_version

HEADER = """# Compatibility matrix

<!-- GENERATED from skills.yaml + capability_catalog.yaml + composition_contracts.yaml — do not edit; run make generate -->

Distribution version: **{version}**

| Skill | Invocation | Cursor | Claude | Kiro | Required capabilities | Write authority |
|-------|------------|--------|--------|------|----------------------|-----------------|
"""


def render_compatibility_matrix(root: Path) -> str:
    registry = load_registry(root)
    capabilities = load_catalog(root / "scripts/registry/capability_catalog.yaml")
    _, _, _, contracts = load_contracts(root / "scripts/registry/composition_contracts.yaml")
    version = read_distribution_version(root)

    lines = [HEADER.format(version=version).rstrip()]
    for skill_id, entry in sorted(registry.skills.items()):
        cap = capabilities.get(skill_id, {})
        contract = contracts.get(skill_id)
        required_list = cap.get("required", []) if isinstance(cap, dict) else []
        any_of = cap.get("any_of", []) if isinstance(cap, dict) else []
        required_alternatives = [", ".join(str(item) for item in required_list)] if required_list else []
        for path in any_of if isinstance(any_of, list) else []:
            if isinstance(path, dict):
                name = str(path.get("name", "path"))
                path_required = path.get("required", [])
                if isinstance(path_required, list):
                    required_alternatives.append(
                        f"{name}: {' + '.join(str(item) for item in path_required)}",
                    )
        required = " OR ".join(required_alternatives) if required_alternatives else "—"
        write_authority = contract.write_authority if contract else "—"
        lines.append(
            f"| `{skill_id}` | {entry.invocation} | {entry.hosts.cursor.discovery} | "
            f"{'yes' if entry.hosts.claude.install else 'no'} | {entry.hosts.kiro.discovery} | "
            f"{required} | {write_authority} |",
        )
    return "\n".join(lines) + "\n"
