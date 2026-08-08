"""Tests for install_support.py."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_list_includes_registered_skill() -> None:
    from scripts.install_support import registry_skill_ids

    ids = registry_skill_ids(ROOT)
    assert "unit-test-creator" in ids
    assert len(ids) == 22


def test_check_rejects_unknown_skill() -> None:
    from scripts.install_support import cmd_check

    assert cmd_check("not-a-real-skill", ROOT) == 1


def test_verify_requires_manifest(tmp_path: Path) -> None:
    from scripts.install_support import cmd_verify

    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    assert cmd_verify(skill_dir) == 1


def test_verify_passes_minimal_package(tmp_path: Path) -> None:
    from scripts.install_support import cmd_verify

    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    manifest = {
        "skill": "demo",
        "source_commit": "abc123",
        "host": "cursor",
        "files": {"SKILL.md": "deadbeef"},
    }
    (skill_dir / ".software-builder-manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    assert cmd_verify(skill_dir) == 0
