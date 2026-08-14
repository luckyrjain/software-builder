"""Every skill must reference the shared result/authorization/completion contracts.

platform_contracts.yaml and runtime-contract.md define skill_result,
action_gates, and definition_of_done once, centrally. This validator makes
sure every registered skill's own SKILL.md actually points back to them,
instead of the contracts existing only as unreferenced scaffolding that no
individual skill is checked against.
"""
from __future__ import annotations

from pathlib import Path

from scripts.registry.models import Registry

REQUIRED_CONTRACT_MARKERS = ("skill_result", "action_gates", "definition_of_done")


def validate_skill_contract_adoption(root: Path, registry: Registry) -> list[str]:
    errors: list[str] = []
    for skill_id, entry in sorted(registry.skills.items()):
        skill_md = root / entry.path / "SKILL.md"
        if not skill_md.is_file():
            continue
        text = skill_md.read_text(encoding="utf-8")
        missing = [marker for marker in REQUIRED_CONTRACT_MARKERS if marker not in text]
        if missing:
            errors.append(
                f"error: {skill_id}: SKILL.md does not reference framework contract(s): "
                + ", ".join(missing),
            )
    return errors
