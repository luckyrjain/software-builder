from __future__ import annotations

from pathlib import Path

from scripts.registry.schema import parse_registry

ROOT = Path(__file__).resolve().parents[2]


def test_registered_skill_entrypoints_stay_within_the_size_budget() -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    for skill_id, entry in registry.skills.items():
        assert entry.lint.skill_md_max_lines <= 180, skill_id
        text = (ROOT / entry.path / "SKILL.md").read_text(encoding="utf-8")
        assert len(text.splitlines()) <= entry.lint.skill_md_max_lines, skill_id


def test_registered_skill_entrypoints_inherit_shared_runtime_contracts() -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    for skill_id, entry in registry.skills.items():
        text = (ROOT / entry.path / "SKILL.md").read_text(encoding="utf-8")
        assert "docs/skill-framework/shared/skill-routing.md" in text, skill_id


def test_core_skill_entrypoints_do_not_branch_on_host_brand() -> None:
    registry = parse_registry(ROOT / "skills.yaml")
    forbidden = ("if cursor", "if claude", "if codex", "if chatgpt", "if kiro")
    for skill_id, entry in registry.skills.items():
        text = (ROOT / entry.path / "SKILL.md").read_text(encoding="utf-8").lower()
        for phrase in forbidden:
            assert phrase not in text, f"{skill_id}: host-specific branch {phrase!r} belongs in an adapter"
