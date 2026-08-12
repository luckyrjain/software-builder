"""Tests for install_support.py."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_SKILL_MD_CONTENT = "# demo\n"
_SKILL_MD_HASH = hashlib.sha256(_SKILL_MD_CONTENT.encode()).hexdigest()


def _write_minimal_package(skill_dir: Path, *, files: dict[str, str] | None = None) -> None:
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")
    manifest = {
        "skill": "demo",
        "source_commit": "abc123",
        "host": "cursor",
        "files": files if files is not None else {"SKILL.md": _SKILL_MD_HASH},
    }
    (skill_dir / ".software-builder-manifest.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )


def test_list_includes_registered_skill() -> None:
    from scripts.install_support import registry_skill_ids

    ids = registry_skill_ids(ROOT)
    assert "unit-test-creator" in ids
    assert len(ids) == 23


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
    _write_minimal_package(skill_dir)
    assert cmd_verify(skill_dir) == 0


def test_verify_rejects_hash_mismatch(tmp_path: Path) -> None:
    from scripts.install_support import cmd_verify

    skill_dir = tmp_path / "demo"
    _write_minimal_package(skill_dir, files={"SKILL.md": "deadbeef"})
    assert cmd_verify(skill_dir) == 1


def test_verify_rejects_file_missing_from_disk(tmp_path: Path) -> None:
    from scripts.install_support import cmd_verify

    skill_dir = tmp_path / "demo"
    _write_minimal_package(
        skill_dir,
        files={"SKILL.md": _SKILL_MD_HASH, "reference/missing.md": "0" * 64},
    )
    assert cmd_verify(skill_dir) == 1


def test_verify_rejects_untracked_extra_file(tmp_path: Path) -> None:
    from scripts.install_support import cmd_verify

    skill_dir = tmp_path / "demo"
    _write_minimal_package(skill_dir)
    (skill_dir / "extra.md").write_text("surprise\n", encoding="utf-8")
    assert cmd_verify(skill_dir) == 1


def test_verify_manifest_files_reports_all_three_cases_together(tmp_path: Path) -> None:
    from scripts.install_support import _verify_manifest_files

    (tmp_path / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")
    (tmp_path / "extra.md").write_text("surprise\n", encoding="utf-8")
    manifest = {
        "files": {
            "SKILL.md": "deadbeef" * 8,
            "reference/missing.md": "0" * 64,
        },
    }

    errors = _verify_manifest_files(tmp_path, manifest)

    assert any("hash mismatch for SKILL.md" in e for e in errors)
    assert any("missing file listed in manifest: reference/missing.md" in e for e in errors)
    assert any("unexpected file not in manifest: extra.md" in e for e in errors)
    assert len(errors) == 3
