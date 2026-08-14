from __future__ import annotations

from pathlib import Path

from scripts.registry.load import load_registry
from scripts.registry.skill_contract_adoption_sync import validate_skill_contract_adoption

ROOT = Path(__file__).resolve().parents[2]


def test_all_registered_skills_reference_the_shared_contracts() -> None:
    registry = load_registry(ROOT)
    assert validate_skill_contract_adoption(ROOT, registry) == []


def test_skill_missing_framework_section_is_rejected(tmp_path: Path) -> None:
    registry = load_registry(ROOT)
    skill_id, entry = next(iter(registry.skills.items()))
    skill_dir = tmp_path / entry.path
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: demo\n---\nNo Framework section here.\n", encoding="utf-8")

    errors = validate_skill_contract_adoption(tmp_path, registry)
    assert any(skill_id in error and "Framework" in error for error in errors)


def test_markers_outside_framework_section_do_not_count(tmp_path: Path) -> None:
    """A stray mention elsewhere in the file must not satisfy adoption."""
    registry = load_registry(ROOT)
    skill_id, entry = next(iter(registry.skills.items()))
    skill_dir = tmp_path / entry.path
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\n---\n"
        "## Notes\n\nWe don't use skill_result, action_gates, or definition_of_done here.\n\n"
        "## Framework\n\nSee runtime-contract.md for shared conventions.\n",
        encoding="utf-8",
    )

    errors = validate_skill_contract_adoption(tmp_path, registry)
    assert any(
        skill_id in error and "skill_result" in error and "action_gates" in error
        for error in errors
    )


def test_markers_inside_framework_section_are_accepted(tmp_path: Path) -> None:
    registry = load_registry(ROOT)
    skill_id, entry = next(iter(registry.skills.items()))
    skill_dir = tmp_path / entry.path
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: demo\n---\n"
        "## Framework\n\n"
        "Emits `skill_result`; classifies against `action_gates`; `definition_of_done`: "
        "required_artifacts=[x]; required_checks=[y]; blocked_conditions=[z]; "
        "partial_result_behavior=w. See runtime-contract.md.\n",
        encoding="utf-8",
    )

    errors = validate_skill_contract_adoption(tmp_path, registry)
    assert not any(skill_id in error for error in errors)
