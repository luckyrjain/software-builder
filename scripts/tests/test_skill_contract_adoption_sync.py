from __future__ import annotations

from pathlib import Path

from scripts.registry.load import load_registry
from scripts.registry.skill_contract_adoption_sync import validate_skill_contract_adoption

ROOT = Path(__file__).resolve().parents[2]


def test_all_registered_skills_reference_the_shared_contracts() -> None:
    registry = load_registry(ROOT)
    assert validate_skill_contract_adoption(ROOT, registry) == []


def test_skill_missing_contract_references_is_rejected(tmp_path: Path) -> None:
    registry = load_registry(ROOT)
    skill_id, entry = next(iter(registry.skills.items()))
    skill_dir = tmp_path / entry.path
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\nNo contract references here.\n", encoding="utf-8")

    errors = validate_skill_contract_adoption(tmp_path, registry)
    assert any(
        skill_id in error and "skill_result" in error and "action_gates" in error
        for error in errors
    )
