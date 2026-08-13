"""Tests for install_support.py."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

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


def test_verify_rejects_non_object_manifest(tmp_path: Path) -> None:
    # json.loads succeeds on any valid JSON document, not just objects --
    # manifest.get("skill") used to be called unconditionally afterward, so
    # a manifest file containing valid-but-non-object JSON (e.g. a JSON
    # array or null) raised an uncaught AttributeError instead of the clean
    # "error: ..." + exit 1 every other malformed-manifest case produces.
    from scripts.install_support import cmd_verify

    skill_dir = tmp_path / "demo"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    (skill_dir / ".software-builder-manifest.json").write_text("[]\n", encoding="utf-8")

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


def test_verify_manifest_files_ignores_pycache_and_ds_store(tmp_path: Path) -> None:
    # Running a skill's own bundled scripts, or ordinary Finder/editor activity,
    # legitimately drops these into an installed directory after a clean install --
    # they must not be treated as tampering.
    from scripts.install_support import _verify_manifest_files

    (tmp_path / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")
    pycache_dir = tmp_path / "scripts" / "__pycache__"
    pycache_dir.mkdir(parents=True)
    (pycache_dir / "helper.cpython-312.pyc").write_bytes(b"\x00")
    (tmp_path / ".DS_Store").write_bytes(b"\x00")
    manifest = {"files": {"SKILL.md": _SKILL_MD_HASH}}

    assert _verify_manifest_files(tmp_path, manifest) == []


def test_verify_manifest_files_rejects_symlink(tmp_path: Path) -> None:
    from scripts.install_support import _verify_manifest_files

    (tmp_path / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")
    outside_target = tmp_path.parent / "outside.txt"
    outside_target.write_text("not part of the package\n", encoding="utf-8")
    (tmp_path / "linked.md").symlink_to(outside_target)
    manifest = {"files": {"SKILL.md": _SKILL_MD_HASH}}

    errors = _verify_manifest_files(tmp_path, manifest)

    assert any("symlink not allowed in installed package: linked.md" in e for e in errors)


def test_verify_manifest_files_symlinked_manifest_entry_reported_once(tmp_path: Path) -> None:
    # A manifest-listed file replaced by a symlink used to trigger two
    # contradictory-sounding errors for the same root cause: "symlink not
    # allowed" AND "missing file listed in manifest" (the symlinked rel never
    # made it into `actual`, so the missing-file check fired too). It should
    # be reported once, via the symlink error.
    from scripts.install_support import _verify_manifest_files

    (tmp_path / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")
    outside_target = tmp_path.parent / "outside2.txt"
    outside_target.write_text("not part of the package\n", encoding="utf-8")
    (tmp_path / "other.md").symlink_to(outside_target)
    manifest = {"files": {"SKILL.md": _SKILL_MD_HASH, "other.md": "0" * 64}}

    errors = _verify_manifest_files(tmp_path, manifest)

    assert any("symlink not allowed in installed package: other.md" in e for e in errors)
    assert not any("missing file listed in manifest: other.md" in e for e in errors)
    assert len(errors) == 1


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="os.mkfifo unavailable on this platform")
def test_verify_manifest_files_rejects_fifo(tmp_path: Path) -> None:
    # Neither is_file() nor is_symlink() is True for a FIFO/socket/device node,
    # so it used to fall through both checks entirely -- silently untracked
    # and unverified, defeating the "installed dir is byte-identical to what
    # was packaged" guarantee this function exists to enforce.
    from scripts.install_support import _verify_manifest_files

    (tmp_path / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")
    fifo_path = tmp_path / "pipe"
    os.mkfifo(fifo_path)
    manifest = {"files": {"SKILL.md": _SKILL_MD_HASH}}

    errors = _verify_manifest_files(tmp_path, manifest)

    assert any("unexpected filesystem entry (not a regular file): pipe" in e for e in errors)


def test_verify_manifest_files_ignores_noise_in_nested_directory(tmp_path: Path) -> None:
    # is_ignored_package_path() used to only check IGNORED_FILE_PATTERNS
    # against the final path component, so a noise-named *directory*
    # anywhere but the immediate parent (e.g. a "backup~" dir two levels
    # down) wasn't recognized as noise even though shutil.ignore_patterns()
    # (used at packaging time) excludes it at every level.
    from scripts.install_support import _verify_manifest_files

    (tmp_path / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")
    noisy_dir = tmp_path / "reference" / "backup~"
    noisy_dir.mkdir(parents=True)
    (noisy_dir / "old.md").write_text("stale\n", encoding="utf-8")
    manifest = {"files": {"SKILL.md": _SKILL_MD_HASH}}

    assert _verify_manifest_files(tmp_path, manifest) == []


def test_verify_manifest_files_reports_unreadable_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # sha256_file() can raise OSError if a manifest-listed file becomes
    # unreadable between the directory scan and the hash read; this must
    # produce a clean error entry, not an uncaught traceback.
    import scripts.install_support as install_support

    (tmp_path / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")
    manifest = {"files": {"SKILL.md": _SKILL_MD_HASH}}

    def _raise(path: Path) -> str:
        raise OSError("permission denied")

    monkeypatch.setattr(install_support, "sha256_file", _raise)

    errors = install_support._verify_manifest_files(tmp_path, manifest)

    assert any("could not read SKILL.md to verify its hash" in e for e in errors)


def test_verify_manifest_files_excludes_nested_manifest_name(tmp_path: Path) -> None:
    # write_manifest() in package_skill.py excludes any file named MANIFEST_NAME
    # anywhere in the tree (matched by basename), not just at the root -- the
    # verify side must agree, or a skill shipping a nested file with that exact
    # name would false-positive as "unexpected file".
    from scripts.install_support import _verify_manifest_files

    (tmp_path / "SKILL.md").write_text(_SKILL_MD_CONTENT, encoding="utf-8")
    nested_dir = tmp_path / "reference"
    nested_dir.mkdir()
    (nested_dir / ".software-builder-manifest.json").write_text("{}\n", encoding="utf-8")
    manifest = {"files": {"SKILL.md": _SKILL_MD_HASH}}

    assert _verify_manifest_files(tmp_path, manifest) == []
