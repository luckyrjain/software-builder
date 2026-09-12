"""Tests for scripts/install_engine.py's uninstall_skill() -- mirrors the ownership-hardening
scenarios scripts/tests/test_install_legacy_golden.py already locks in for install.sh's
uninstall path."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.install_engine import uninstall_skill


def _owned_install(dest_root: Path, skill_id: str) -> Path:
    dest = dest_root / skill_id
    dest.mkdir(parents=True)
    (dest / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    (dest / ".software-builder-manifest.json").write_text(
        json.dumps({"manifest_version": 1, "skill": skill_id, "files": {}}), encoding="utf-8"
    )
    return dest


def test_uninstall_removes_an_owned_install(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest = _owned_install(dest_root, "demo-skill")

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "uninstalled"
    assert not dest.exists()


def test_uninstall_of_absent_skill_warns_without_failing(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest_root.mkdir()

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "absent"


def test_uninstall_refuses_to_remove_a_symlink(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest_root.mkdir()
    target = tmp_path / "elsewhere"
    target.mkdir()
    (dest_root / "demo-skill").symlink_to(target)

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "failed"
    assert "symlink" in outcome.message.lower()
    assert (dest_root / "demo-skill").is_symlink()  # untouched


def test_uninstall_refuses_to_remove_an_unowned_directory(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest = dest_root / "demo-skill"
    dest.mkdir(parents=True)
    (dest / "some-other-file.txt").write_text("not ours\n", encoding="utf-8")

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "failed"
    assert "unowned" in outcome.message.lower()
    assert dest.exists()


def test_uninstall_refuses_to_remove_a_directory_with_corrupt_manifest(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest = dest_root / "demo-skill"
    dest.mkdir(parents=True)
    (dest / ".software-builder-manifest.json").write_text("not valid json", encoding="utf-8")

    outcome = uninstall_skill("demo-skill", dest_root=dest_root)

    assert outcome.status == "failed"
    assert dest.exists()


def test_uninstall_dry_run_makes_no_changes(tmp_path: Path) -> None:
    dest_root = tmp_path / "dest"
    dest = _owned_install(dest_root, "demo-skill")

    outcome = uninstall_skill("demo-skill", dest_root=dest_root, dry_run=True)

    assert outcome.status == "dry_run"
    assert dest.exists()
